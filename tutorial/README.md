# Getting started with the SYNTHETIC package


## Test the installation

Right now the best way to run this package is via a pre set conda environment. 

At the moment this is available in the LMU USM server, and is planned to be added for the NERSC LSST DESC server.

On the USM you should use the following command to activate the environment 
    
    conda activate /home/moon/vargatn/anaconda3/envs/galsim

and use the [checkup script](./env_checkup.py)

    python env_checkup.py

If this runs without errors, then you are set to go!

*TBA* hands on dependency install instructions..

## Part A: The generative model

:red_circle: **A1** [Prepare catalog](A1_prepare_catalogs.ipynb)
* status:  TBA

:red_circle: **A2** [Train cluster model](A2_train_cluster_model.ipynb)
* status:  TBA

:yellow_circle: **A3**  [Work with galaxy distributions](A3_work_with_galaxy_distributions.ipynb)
* status:  scope added, needs further figures and descriptions

:red_circle: **A4**  [Draw cluster catalog](A4_draw_cluster_catalog.ipynb)
* status:  TBA

## Part B: Rendering images

:yellow_circle: **B1**  [Render images from catalog](B1_render_image.ipynb)
* status:  scope added, needs description

:red_circle: **B2**  [Inject images to catalog](B2_inject_image.ipynb)
* status:  TBA

:red_circle: **B3**  [Add intra-cluster light (ICL) to images](B3_add_icl.ipynb)
* status:  TBA

## Part C: Processing with metacalibration

:red_circle: **C1**  [Running sextractor](C1_running_sextractor.ipynb)
* status:  TBA

:red_circle: **C2**  [create MEDS](C2_creat_MEDS.ipynb)
* status:  TBA

:red_circle: **C3**  [metacalibration on a grid](C3_metacal_on_a_grid.ipynb)
* status:  TBA

:red_circle: **C4**  [metacalibration of cluster injection](C4_metacal_on_cluster_injections.ipynb)
* status:  TBA