"""
Galsim rendering backend

the first stretch goal is to build a stand alone renderer which is encapsulated in a class. The

# TODO add input catalog specification here

# TODO add color composite image creator function

"""

import numpy as np
import galsim
import ngmix
import pandas as pd
import multiprocessing as mp
from ..tools import partition, toflux


def radec2xy(ra, dec, sky_center,  pixel_scale=0.2, image_offset=(2499.5, 2499.5)):
    """
    Converts RA DEC position to image position

    Parameters
    ----------
    ra: deg
        right ascension
    dec: deg
        declination
    sky_center: tuple
        ra_center, dec_center
    pixel_scale: float
        pixel scale
    image_offset: tuple
        image_centers, default is (2499.5, 2499.5)

    Returns
    -------
        X, Y values

    """
    x = (ra - sky_center[0]) * 60 * 60 / pixel_scale + image_offset[0]
    y = (dec - sky_center[1]) * 60 * 60 / pixel_scale + image_offset[1]
    return x.values, y.values


def draw_info(info):
    """
    Creates a postage stamp image based on the info dictionary

            bdf_pars = info["bdf_pars"]
            psf = info["psf"]
            pixel_scale = info["pixel_scale"]
            x_cen = info["x_cen"]       # in pixels
            y_cen = info["y_cen"]       # in pixels
            offset = info["offset"]     # in pixels

    Parameters
    ----------
    info: dict
        dictionary with the properties of the object to draw

    Returns
    -------
        postage stamp, bounding box, id of the object

    """
    bdf_pars = info["bdf_pars"]
    psf = info["psf"]
    pixel_scale = info["pixel_scale"]
    x_cen = info["x_cen"]
    y_cen = info["y_cen"]
    offset = info["offset"]

    galmaker = ngmix.gmix.GMixBDF(bdf_pars)
    gs_profile = galmaker.make_galsim_object()
    final_gal = galsim.Convolve([psf, gs_profile])
    stamp_size = final_gal.getGoodImageSize(pixel_scale)

    bound = galsim.BoundsI(x_cen - stamp_size / 2 + 1, x_cen + stamp_size / 2,
                           y_cen - stamp_size / 2 + 1, y_cen + stamp_size / 2)

    stamp = galsim.ImageF(bound, scale=pixel_scale, )
    final_gal.drawImage(stamp, offset=offset, )

    return stamp, bound, info["id"]

def call_chunks(infodicts):
    """Technically this is inside the multiprocessing call, so it should not change any self properties"""
    stamps = []
    bounds = []
    ids = []
    for info in infodicts:
        stamp, bound, i = draw_info(info)
        stamps.append(stamp)
        bounds.append(bounds)
        ids.append(i)

    return stamps, bounds, ids

#TODO make more elegant via galsim


class DrawField(object):
    def __init__(self, canvas_size, catalog, center=(0., 0.), band="g", pixel_scale=0.2, sky_level=1.e2, psf_fwhm=0.9):
        """
        Drawer object to create an image from a galaxy catalog

        This assumes a gaussian PSF

        Parameters
        ----------
        canvas_size: int

        catalog: pd.DataFrame
            galaxy catalog to render
        center: tuple
            image center
        band: str
            optical band as a string e.g. "g" or "r" or "i",
        pixel_scale: float
            pixel scale
        sky_level: float
            Std for sky noise
        psf_fwhm: float
            FWHM of the PSF model for gaussian

        """
        self.canvas_size = canvas_size
        self.catalog = catalog
        self.band = band
        self.pixel_scale = pixel_scale
        self.sky_level = sky_level
        self.psf_fwhm = psf_fwhm
        self.center = center

        self.stamps = []
        self.stamps_bounds = []
        self.positions = []
        self.offsets = []

    def render(self, nprocess=10):
        """
        Renders galaxy catalog into postage stamps and then collates them into an image canvas

        Current multicore support is not ideal

        Parameters
        ----------
        nprocess: int
            number of cores to use
        """
        self.prepare()
        self.make_infodicts()
        self.multi_render(nprocess)
        self.collate_stamps()

    def make_canvas(self):
        """Create canvas for rendering"""
        self.xx = self.catalog['X']
        self.yy = self.catalog['Y']
        self.canvas = galsim.ImageF(self.canvas_size, self.canvas_size, scale=self.pixel_scale)
        #self.canvas.array[:, :] = 0  # this might be redundant

    def make_wcs(self):
        """
        Create internal WCS object
        """
        # If you wanted to make a non-trivial WCS system, could set theta to a non-zero number
        theta = 0.0 * galsim.degrees
        dudx = np.cos(theta) * self.pixel_scale
        dudy = -np.sin(theta) * self.pixel_scale
        dvdx = np.sin(theta) * self.pixel_scale
        dvdy = np.cos(theta) * self.pixel_scale
        image_center = self.canvas.true_center
        affine = galsim.AffineTransform(dudx, dudy, dvdx, dvdy, origin=self.canvas.true_center)
        sky_center = galsim.CelestialCoord(ra=self.center[0] * galsim.degrees, dec=self.center[1]* galsim.degrees)

        self.wcs = galsim.TanWCS(affine, sky_center, units=galsim.arcsec)
        self.canvas.wcs = self.wcs

    def make_psf(self):
        """
        Creates the PSF (point spread function) for the image rendering
        """
        self.psf = galsim.Gaussian(fwhm=self.psf_fwhm)
        self.image_epsf = self.psf.drawImage(scale=self.pixel_scale, )

    def make_bdf_pars(self):
        """
        Calculate parameters for each object according to metacal BDF model

        1: X position
        2: Y position
        3: G1 shape
        4: G4 shape
        5: TSIZE (xsize**2 + ysize**2)
        6: Morphology fracdev (DeVauceoulours fraction)
        7: Flux of the source
        """
        self.bdf_pars = np.zeros((len(self.catalog), 7))
        # There might be a way to add xoffset and yoffset here also as 0 and 1 element
        self.bdf_pars[:, 2] = self.catalog["G1"][:]
        self.bdf_pars[:, 3] = self.catalog["G2"][:]
        self.bdf_pars[:, 4] = self.catalog["TSIZE"][:]
        self.bdf_pars[:, 5] = self.catalog["FRACDEV"][:]
        self.bdf_pars[:, 6] = self.catalog["FLUX_" + self.band.upper()][:]

    def make_positions(self):
        """Transforms source positions into image canvas positions, and postage stamp offsets"""
        self.xx = self.catalog['X'][:]# - self.canvas.true_center.x
        self.yy = self.catalog['Y'][:]# - self.canvas.true_center.y

        self.x_cen = np.floor(self.xx)
        self.y_cen = np.floor(self.yy)
        
        self.offsets = np.vstack((self.xx - self.x_cen, self.yy - self.y_cen)).T

    def prepare(self):
        """Prepare canvas, psf, metacal parameters, and pre-calculates positions"""
        self.make_canvas()
        self.make_psf()
        self.make_bdf_pars()
        self.make_positions()

    def make_infodicts(self):
        """Prepare instruction set dictionaries to be passed for multiprocessing calculations"""
        self.infodicts = []
        for i in np.arange(len(self.catalog)):
            info = {
                "id": i,
                "bdf_pars": self.bdf_pars[i],
                "psf": self.psf,
                "pixel_scale": self.pixel_scale,
                "x_cen": self.x_cen[i],
                "y_cen": self.y_cen[i],
                "offset": self.offsets[i]
            }
            self.infodicts.append(info)

    def multi_render(self, nprocess=1):
        """
        OpenMP style parallelization for xshear tasks
        Separates tasks into chunks, and passes each chunk for an independent process
        for serial evaulation via :py:func:`call_chunks`
        Parameters
        ----------
        infodict : dict
            A single list element returned from :py:func:`create_infodict`
        nprocess : int
            Number of processes (cores) to use. Maximum number is always set by ``len(infodicts)``
        """
        # at most as many processes can be used as there are independent tasks...
        if nprocess > len(self.infodicts):
            nprocess = len(self.infodicts)

        print('starting postage stamp calculations in ' + str(nprocess) + ' processes')
        fparchunks = partition(self.infodicts, nprocess)
        pool = mp.Pool(processes=nprocess)

        self.stamps, self.bounds, self.ids = [], [], []
        try:
            pp = pool.map_async(call_chunks, fparchunks)
            res = pp.get()  # apparently this counters a bug in the exception passing in python.subprocess...

            for tmp in res:
                self.stamps += tmp[0]
                self.bounds += tmp[1]
                self.ids += tmp[2]

        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt, terminating workers")
            pool.terminate()
            pool.join()
        else:
            pool.close()
            pool.join()

    def collate_stamps(self):
        """
        Add together all postage stamps to create the rendered image
        """
        for i in np.arange(len(self.catalog)):
            try:
                stamp = self.stamps[i]
                bb = stamp.bounds & self.canvas.bounds
                self.canvas[bb] += stamp[bb]
            except galsim.errors.GalSimBoundsError:
                pass

    def add_icl(self, arr):
        """
        Adds the ICL layer to the image canvas

        Parameters
        ----------
        arr: galsim.Image
            galsim Image of the ICL rendered

        """
        self.canvas += arr

#
# def scale_image(canvas):
#     """Applies arc"""
#     try:
#         res = np.arcsinh(canvas) / canvas
#     except:
#         res = np.arcsinh(canvas.array) / canvas.array
#     return re
#
#


