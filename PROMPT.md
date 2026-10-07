Follow AGENTS.md.

Let us build a visualization plotter for ferromagnetic resonance measurements for thin films of magnetic insulator. Let us assume that this was a thin film with in magnetic anisotropy that is as high as 0.9 T. 

The way we did the experiment - we applied an in-plane static magnetic field and then applied a modulation field to allow us to detect the signal using a lock-in amplifier since we did not have a microwave signal detectors like a VNA. 
We did magnetic field sweeps at different frequencies. Each file has the frequency on the file name and the data inside the file is such that the first column is the magnetic field in Oe and the second column is the signal from the lock-in.

I would like to visual the FMR frequency vs field on one plot and then linewidth vs frequency on another plot. 

For the FMR frequency vs field - we should fit the kittel equation for a thin film with in-plane magnetic anisotropy. We want to extract the uniaxial out of plane anisotropy and four fold in-plane magnetic anisotropy as well as the Lande G factor. 

Then use the Lane g factor to extract damping from the linewidth vs frequency fitting. SHow the equations you fit in the plots. 

We want to build a webapp that we can visualize only on the computer which means you are to build a fastAPI exposing the localhost port. 
