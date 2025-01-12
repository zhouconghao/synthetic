
import numpy as np
import subprocess
import fitsio as fio
import galsim

from . import shear
from . import render

# TODO automate sextractor config file path

class MockPSF(object):
    def __init__(self, psf_image):
        """This is a hacked PSFex solution, giving directly the psf image"""
        self.psf_image = psf_image

    def get_center(self, *args, **kwargs):
        """Only called by the MEDS maker"""
        center = self.psf_image.center
        return center.x, center.y

    def get_rec(self, *args, **kwargs):
        """Only called by teh MEDS maker"""
        return self.psf_image.array


class Frame(object):
    def __init__(self, catalog, name="canvas", canvas_size=5000, center=(0., 0.), band="i", noise_std=8.36, config_se="config.sex", pixel_scale=0.2):
        """
        Wrapper for creating synthetic images from galaxy catalogs, then running metacalibration on them

        Parameters
        ----------
        catalog: pd.DataFrame
            galaxy catalog to render
        name: str
            name tag of the frame
        canvas_size: int
            size of the rectangular canvas in pixels
        center: tuple
            center of the image in RA, DEC
        band: str
            photometric band str as "g" or "r" or "i"
        noise_std: float
            standard deviation of the gaussian sky noise
        config_se: str
            file name of the SExtractor config file
        pixel_scale: float
            pixel scale
        """
        self.catalog = catalog
        self.canvas_size = canvas_size
        self.band = band
        self.noise_std = noise_std
        self.name = name
        self.config_se = config_se
        self.pixel_scale = pixel_scale
        self.center = center

    def render(self, nprocess=1):
        """Render the synthetic image from galaxy catalog, wraps the render.DrawField class"""
        self.df = render.DrawField(self.canvas_size, self.catalog, center=self.center, band=self.band)
        self.df.prepare()
        self.df.make_wcs()
        self.df.make_infodicts()
        self.df.multi_render(nprocess)
        self.df.collate_stamps()
        self.canvas = self.df.canvas

        self.noise = np.random.normal(scale=self.noise_std, size=(self.canvas_size, self.canvas_size))
        self.canvas += self.noise

        self.write()

    def write(self):
        """
        Write the rendered image and PSF info into file

        file name is determined from the initiated self.name + .fits
        psf file name is self.name + _epsf.fits
        """
        self.file_name = self.name + ".fits"
        self.canvas.write(self.file_name, clobber=True)
        #fio.write(self.file_name, self.canvas.array, clobber=True)
        self.file_name_psf = self.name + "_epsf.fits"
        #fio.write(self.file_name_psf, self.df.image_epsf.array, clobber=True)
        self.df.image_epsf.write(self.file_name_psf, clobber=True)

    def extract(self):
        """
        Runs Source Extractor on the image, and calculates the segmentation map

        Outputs are written to file

        self.file_name = self.name + ".fits"
        self.catalog_name = self.name + "_cat.fits"
        self.seg_name = self.name + "_seg.fits"
        """
        self.file_name = self.name + ".fits"
        self.catalog_name = self.name + "_cat.fits"
        self.seg_name = self.name + "_seg.fits"
        #self.weight_name = self.name + "_wmap.fits"

        cmd = "sex " + self.name + ".fits -c " + self.config_se + " -CATALOG_NAME " + self.catalog_name + " -CHECKIMAGE_NAME " + self.seg_name
        print(cmd)
        pp = subprocess.Popen(cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = pp.communicate()

        self.scat = fio.read(self.catalog_name)
        self.seg = fio.read(self.seg_name)

    def ksb(self):
        """
        Calculates the shear using KSB through galsim, wraps the render.shear.Shear class
        """
        self.file_name = self.name + ".fits"
        self.catalog_name = self.name + "_cat.fits"
        self.seg_name = self.name + "_seg.fits"

        self.scat = fio.read(self.catalog_name)
        self.seg = fio.read(self.seg_name)
        self.file_name_psf = self.name + "_epsf.fits"
        self.epsf = fio.read(self.file_name_psf)

        canvas = fio.read(self.file_name)
        self.canvas = galsim.ImageF(canvas)

        self.ids = self.scat['NUMBER']
        self.cens = np.vstack((self.scat['X_IMAGE'], self.scat['Y_IMAGE'])).T
        self.sizes = np.around(self.scat["FWHM_IMAGE"] * 2)
        self.sizes = np.max((np.zeros(len(self.sizes)) + 8, self.sizes), axis=0)
        self.sc = shear.Shear(self.canvas, self.epsf, self.seg, self.pixel_scale)
        self.sc.extract_stamps(self.cens, imasks=self.ids, sizes=self.sizes)
        self.sc.estimate_shear(sky_var=self.noise_std**2)