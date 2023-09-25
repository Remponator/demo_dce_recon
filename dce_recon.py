import argparse
import h5py
import os

import numpy as np
import sigpy as sp
import torch

from sigpy.mri import app

DIR = os.path.dirname(os.path.realpath(__file__))

# %%
def get_traj(N_spokes=13, N_time=1, base_res=320, gind=1):

    N_tot_spokes = N_spokes * N_time

    N_samples = base_res * 2

    base_lin = np.arange(N_samples).reshape(1, -1) - base_res

    tau = 0.5 * (1 + 5**0.5)
    base_rad = np.pi / (gind + tau - 1)

    base_rot = np.arange(N_tot_spokes).reshape(-1, 1) * base_rad

    traj = np.zeros((N_tot_spokes, N_samples, 2))
    traj[..., 0] = np.cos(base_rot) @ base_lin
    traj[..., 1] = np.sin(base_rot) @ base_lin

    traj = traj / 2

    traj = traj.reshape(N_time, N_spokes, N_samples, 2)

    return np.squeeze(traj)

# %% compute coil sensitivity maps
def get_coil(ksp, device=sp.Device(-1)):

    N_coils, N_spokes, N_samples = ksp.shape

    base_res = N_samples // 2

    ishape = [N_coils] + [base_res] * 2

    traj = get_traj(N_spokes=N_spokes, N_time=1,
                    base_res=base_res, gind=1)

    dcf = (traj[..., 0]**2 + traj[..., 1]**2)**0.5

    F = sp.linop.NUFFT(ishape, traj)

    cim = F.H(ksp * dcf)
    cim = sp.fft(cim, axes=(-2, -1))

    mps = app.EspiritCalib(cim, device=device).run()
    return sp.to_device(mps)


# %%
if __name__ == "__main__":

    # %% parse
    parser = argparse.ArgumentParser(description='run dce reconstruction.')

    parser.add_argument('--data',
                        default='GeneBreast_CCCTrio#F636203.h5',
                        help='radial k-space data')

    parser.add_argument('--spokes_per_frame', type=int, default=12,
                        help='number of spokes per frame')

    parser.add_argument('--slice_idx', type=int, default=0,
                        help='which slice index for the reconstruction to begin with')

    parser.add_argument('--slice_inc', type=int, default=1,
                        help='number of slices to be reconstructed')

    args = parser.parse_args()

    device = sp.Device(0 if torch.cuda.is_available() else -1)
    print('> device ', device)

    # %% read in k-space data
    print('> read in data ', args.data)
    f = h5py.File(args.data, 'r')
    ksp_f = f['kspace'][:].T
    f.close()

    ksp = ksp_f[0] + 1j * ksp_f[1]
    ksp = np.transpose(ksp, (3, 2, 0, 1))

    # zero-fill the slice dimension
    ksp_zf = sp.resize(ksp, oshape=[192] + list(ksp.shape[1:]))
    ksp_zf = sp.fft(ksp_zf, axes=(0,))

    N_slices, N_coils, N_spokes, N_samples = ksp_zf.shape




    base_res = N_samples // 2

    N_time = N_spokes // args.spokes_per_frame

    N_spokes_prep = N_time * args.spokes_per_frame

    ksp_redu = ksp_zf[:, :, :N_spokes_prep, :]
    print('  ksp_redu shape: ', ksp_redu.shape)

    # %% retrospecitvely split spokes
    ksp_prep = np.swapaxes(ksp_redu, 0, 2)
    ksp_prep_shape = ksp_prep.shape
    ksp_prep = np.reshape(ksp_prep, [N_time, args.spokes_per_frame] + list(ksp_prep_shape[1:]))
    ksp_prep = np.transpose(ksp_prep, (3, 0, 2, 1, 4))
    ksp_prep = ksp_prep[:, :, None, :, None, :, :]
    print('  ksp_prep shape: ', ksp_prep.shape)

    # %% trajectories
    traj = get_traj(N_spokes=args.spokes_per_frame,
                    N_time=N_time, base_res=base_res,
                    gind=1)
    print('  traj shape: ', traj.shape)

    # %% slice-by-slice recon

    if args.slice_idx >= 0:
        slice_loop = range(args.slice_idx, args.slice_idx + args.slice_inc, 1)
    else:
        slice_loop = range(N_slices)

    for s in slice_loop:
        print('>>> slice ', str(s).zfill(3))

        # coil sensitivity maps
        print('> compute coil sensitivity maps')
        C = get_coil(ksp_zf[s], device=device)
        C = C[:, None, :, :]
        print('  coil shape: ', C.shape)

        # recon
        k1 = ksp_prep[s]
        R1 = app.HighDimensionalRecon(k1, C,
                        combine_echo=False,
                        lamda=0.001,
                        coord=traj,
                        regu='TV', regu_axes=[0],
                        max_iter=10,
                        solver='ADMM', rho=0.1,
                        device=device,
                        show_pbar=False,
                        verbose=True).run()

        R1 = sp.to_device(R1)

        # save recon files
        f = h5py.File(DIR + '/reco_slice' + str(s).zfill(3) + '.h5', 'w')
        f.create_dataset('temptv', data=R1)
        f.close()