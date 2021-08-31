# PyTorch
import torch
from torch.utils.data import DataLoader
from torch import nn, optim
from torch.autograd import Variable
import torch.nn.functional as F

# Form cost matrices
from scipy.spatial.distance import cdist

# Typing
from typing import List, Set, Dict, Tuple, Optional
from typing import Callable, Iterator, Union, Optional, List

# Numpy
import numpy as np

# Biology
import scanpy as sc
import anndata as ad

# Nonnegative least squares
import nn_fac.nnls

# Progress bar
from tqdm import tqdm

import matplotlib.pyplot as plt

class iNMF():
    def __init__(self, n_features_1: int, n_features_2: int,
                 n_cells: int, latent_dim: int, lbda: float = 5):
        # Dimensions
        self.n_features_1 = n_features_1
        self.n_features_2 = n_features_2
        self.n_cells = n_cells
        self.latent_dim = latent_dim

        # Reg
        self.lbda = lbda

        # Initialize
        self.init()

        # Losses
        self.losses = []

    def init(self):
        # Init
        self.W = np.random.rand(self.latent_dim, self.n_cells)
        self.V1 = np.random.rand(self.latent_dim, self.n_cells)
        self.V2 = np.random.rand(self.latent_dim, self.n_cells)
        self.H1 = np.random.rand(self.n_features_1, self.latent_dim)
        self.H2 = np.random.rand(self.n_features_2, self.latent_dim)

        # Keep initialization
        self.W_init = self.W.copy()
        self.V1_init = self.V1.copy()
        self.V2_init = self.V2.copy()
        self.H1_init = self.H1.copy()
        self.H2_init = self.H2.copy()

    def nnls(self, A: np.ndarray, B: np.ndarray,
             X_init: np.ndarray) -> np.ndarray:
        # solve min ||AX - B|| s.t. X > 0
        return nn_fac.nnls.hals_nnls_acc(A.T @ B, A.T @ A, X_init)[0]

    def fit(self, adata_1: ad.AnnData, adata_2: ad.AnnData, n_iter: int = 20):
        A1, A2 = adata_1.X.T, adata_2.X.T
        self.losses = []
        for _ in tqdm(range(n_iter)):
            # Optimize H1
            W_tilde = np.vstack((
                self.W.T + self.V1.T,
                np.sqrt(self.lbda)*self.V1.T
            ))
            obj = np.vstack((A1.T, np.zeros_like(A1.T)))
            self.H1 = self.nnls(W_tilde, obj, self.H1_init.T).T

            # Optimize H2
            W_tilde = np.vstack((
                self.W.T + self.V2.T,
                np.sqrt(self.lbda)*self.V2.T
            ))
            obj = np.vstack((A2.T, np.zeros_like(A2.T)))
            self.H2 = self.nnls(W_tilde, obj, self.H2_init.T).T

            # Optimize V1
            H_tilde = np.vstack((self.H1, np.sqrt(self.lbda)*self.H1))
            obj = np.vstack((A1 - self.H1 @ self.W, np.zeros_like(A1)))
            self.V1 = self.nnls(H_tilde, obj, self.V1_init)

            # Optimize V2
            H_tilde = np.vstack((self.H2, np.sqrt(self.lbda)*self.H2))
            obj = np.vstack((A2 - self.H2 @ self.W, np.zeros_like(A2)))
            self.V2 = self.nnls(H_tilde, obj, self.V2_init)

            # Optimize W
            H_tilde = np.vstack((self.H1, self.H2))
            obj = np.vstack((A1 - self.H1 @ self.V1, A2 - self.H2 @ self.V2))
            self.W = self.nnls(H_tilde, obj, self.W_init)

            self.losses.append(0)
            self.losses[-1] += np.linalg.norm(A1 - self.H1@(self.W + self.V1))
            self.losses[-1] += np.linalg.norm(A2 - self.H2@(self.W + self.V2))
            self.losses[-1] += self.lbda*np.linalg.norm(self.H1 @ self.V1)
            self.losses[-1] += self.lbda*np.linalg.norm(self.H2 @ self.V2)

class intNMF():
    def __init__(self, n_features_1: int, n_features_2: int,
                 n_cells: int, latent_dim: int, p1: float = .7, p2: float = .3):
        # Dimensions
        self.n_features_1 = n_features_1
        self.n_features_2 = n_features_2
        self.n_cells = n_cells
        self.latent_dim = latent_dim

        self.p1 = p1
        self.p2 = p2

        # Initialize
        self.init()

        # Losses
        self.losses = []

    def init(self):
        # Init
        self.W = np.random.rand(self.latent_dim, self.n_cells)
        self.H1 = np.random.rand(self.n_features_1, self.latent_dim)
        self.H2 = np.random.rand(self.n_features_2, self.latent_dim)

        # Keep initialization
        self.W_init = self.W.copy()
        self.H1_init = self.H1.copy()
        self.H2_init = self.H2.copy()

    def nnls(self, A: np.ndarray, B: np.ndarray,
             X_init: np.ndarray) -> np.ndarray:
        # solve min ||AX - B|| s.t. X > 0
        return nn_fac.nnls.hals_nnls_acc(A.T @ B, A.T @ A, X_init)[0]

    def fit(self, adata_1: ad.AnnData, adata_2: ad.AnnData, n_iter: int = 20):
        A1, A2 = adata_1.X.T, adata_2.X.T
        self.losses = []
        for _ in tqdm(range(n_iter)):
            # Optimize H1
            self.H1 = self.nnls(self.W.T, A1.T, self.H1_init.T).T

            # Optimize H2
            self.H2 = self.nnls(self.W.T, A2.T, self.H1_init.T).T

            # Optimize W
            H_tilde = np.vstack((self.p1*self.H1, self.p2*self.H2))
            obj = np.vstack((self.p1*A1, self.p2*A2))
            self.W = self.nnls(H_tilde, obj, self.W_init)

            self.losses.append(0)
            self.losses[-1] += np.linalg.norm(A1 - self.H1@self.W)
            self.losses[-1] += np.linalg.norm(A2 - self.H2@self.W)

class OTintNMF():
    def __init__(self, latent_dim=15, rho_h=1e-1, rho_w=1e-1, lr=1e-2, eps=5e-2, tol=1e-2):
        self.latent_dim = latent_dim

        self.lr = lr

        self.rho_h = rho_h
        self.rho_w = rho_w
        self.eps = eps

        self.tol = tol

    def build_optimizer(self, params, lr):
        return optim.LBFGS(params, lr=lr, history_size=10, max_iter=4)

    def entropy(self, X, min_one=False):
        if min_one:
            return -(X*(X.log()-1)).sum()
        else:
            return -(X*X.log()).sum()

    def entropy_dual_loss(self, X):
        # For entropy defined on the simplex!
        # min_one=False
        return -torch.logsumexp(X, dim=0).sum()

    def ot_dual_loss(self, A, K, G):
        loss = self.entropy(A, min_one=True)
        loss += (A*torch.log(K@torch.exp(G/self.eps))).sum()
        return self.eps*loss

    def optimize(self, modalities, n_iter_inner, n_iter, device, K):
        optimizer_h, self.losses_h, self.losses_w  = {}, {}, []
        for mod in modalities: # For each modality...
            optimizer_h[mod] = self.build_optimizer([self.GH[mod]], lr=self.lr)
            self.losses_h[mod] = []
        optimizer_w = self.build_optimizer([self.GW[mod] for mod in modalities], lr=self.lr)

        # Progress bar
        pbar = tqdm(total=n_iter_inner*2*len(modalities)*n_iter, position=0, leave=True)

        # Losses
        loss_h = {}

        # Main loop
        for k in range(n_iter):
            # Dual solver for H_i
            for mod in modalities:
                def closure():
                    optimizer_h[mod].zero_grad()
                    loss_h[mod] = self.ot_dual_loss(self.A[mod], K[mod], self.GH[mod])
                    loss_h[mod] -= self.rho_h*self.entropy_dual_loss(-self.GH[mod]@self.W.T/self.rho_h)
                    self.losses_h[mod].append(loss_h[mod].detach())
                    loss_h[mod].backward()
                    return loss_h[mod]
                for _ in range(n_iter_inner):
                    optimizer_h[mod].step(closure)
                    pbar.update(1)

                self.H[mod] = F.softmin(self.GH[mod]@self.W.T/self.rho_h, dim=0).detach()

            # Dual solver for W
            def closure():
                optimizer_w.zero_grad()
                loss_w = 0
                htgw = 0
                for mod in modalities:
                    htgw += self.H[mod].T@self.GW[mod]
                    loss_w += self.ot_dual_loss(self.A[mod], K[mod], self.GW[mod])
                loss_w -= len(modalities)*self.rho_w*self.entropy_dual_loss(-htgw/(len(modalities)*self.rho_w))
                self.losses_w.append(loss_w.detach())
                loss_w.backward()
                return loss_w
            for _ in range(n_iter_inner):
                optimizer_w.step(closure)
                pbar.update(len(modalities))

            htgw = 0
            for mod in modalities:
                htgw += self.H[mod].T@self.GW[mod]
            self.W = F.softmin(htgw/(len(modalities)*self.rho_w), dim=0).detach()

            pbar.set_postfix(loss=self.losses_w[-1].cpu().numpy())

            if len(self.losses_w) > 2 and abs(self.losses_w[-1] - self.losses_w[-2]) <= self.tol:
                break

    def update_latent_dim(self, mdata, latent_dim, n_iter_inner=25, n_iter=25, device='cpu', dtype=torch.float):
        assert(latent_dim > self.latent_dim)
        self.latent_dim = latent_dim
        K = {}
        A_tilde = {}
        H_old = {}
        for mod in mdata.mod:
            # Compute K
            # ... Generate datasets
            self.A[mod] = mdata[mod].X[:,mdata[mod].var['highly_variable'].to_numpy()]
            try:
                self.A[mod] = self.A[mod].todense()
            except:
                pass

            # Normalize datasets
            self.A[mod] = 1e-6 + self.A[mod].T
            self.A[mod] /= self.A[mod].sum(0)

            C = torch.from_numpy(cdist(self.A[mod], self.A[mod], metric=self.cost)).to(device=device, dtype=dtype)
            C /= C.max()
            K[mod] = torch.exp(-C/self.eps).to(device=device, dtype=dtype)

            self.A[mod] = torch.from_numpy(self.A[mod]).to(device=device, dtype=dtype)

            # Compute residual
            A_tilde[mod] = self.A[mod] - self.H[mod] @ self.W
            A_tilde[mod] = torch.abs(A_tilde[mod])
            A_tilde[mod] = 1e-6 + A_tilde[mod]
            A_tilde[mod] /= A_tilde[mod].sum(0)

            # ... Generate H_i
            H_old[mod] = 1.*self.H[mod]
            self.H[mod] = torch.rand(self.H[mod].shape[0], self.latent_dim - self.H[mod].shape[1], device=device, dtype=dtype)
            self.H[mod] /= self.H[mod].sum(0)

            # ... Generate G_{H_i}
            self.GH[mod] = torch.rand(self.GH[mod].shape[0], mdata[mod].n_obs, requires_grad=True, device=device, dtype=dtype)

            # ... Generate G_{W_i}
            self.GW[mod] = torch.rand(self.GW[mod].shape[0], mdata[mod].n_obs, requires_grad=True, device=device, dtype=dtype)

        # Generate W
        W_old = 1.*self.W
        self.W = torch.rand(self.latent_dim - self.W.shape[0], self.W.shape[1], device=device, dtype=dtype)
        self.W /= self.W.sum(0)

        self.A = A_tilde

        self.optimize(modalities=mdata.mod, n_iter_inner=n_iter_inner, n_iter=n_iter, device=device, K=K)

        for mod in mdata.mod:
            mdata[mod].uns['H_OT'] = torch.cat([H_old[mod], self.H[mod]], dim=1)
        mdata.obsm['W_OT'] = torch.cat([W_old, self.W], dim=0).T

    def plot_convergence(self):
        plt.title('Dual losses for H')
        for mod in self.H:
            plt.plot(self.losses_h[mod])
        plt.legend(self.H.keys())
        plt.show()

        plt.title('Dual loss for W')
        plt.plot(self.losses_w)
        plt.show()

    def fit_transform(self, mdata, cost='cosine', n_iter_inner=25, n_iter=25, device='cpu', dtype=torch.float):
        self.A, self.H, self.GH, self.GW, K = {}, {}, {}, {}, {}
        self.cost = cost

        for mod in mdata.mod: # For each modality...

            # ... Generate datasets
            self.A[mod] = mdata[mod].X[:,mdata[mod].var['highly_variable'].to_numpy()]
            try:
                self.A[mod] = self.A[mod].todense()
            except:
                pass

            # Normalize datasets
            self.A[mod] = 1e-6 + self.A[mod].T
            self.A[mod] /= self.A[mod].sum(0)

            # Compute K
            C = torch.from_numpy(cdist(self.A[mod], self.A[mod], metric=self.cost)).to(device=device, dtype=dtype)
            C /= C.max()
            K[mod] = torch.exp(-C/self.eps).to(device=device, dtype=dtype)

            # send to PyTorch
            self.A[mod] = torch.from_numpy(self.A[mod]).to(device=device, dtype=dtype)

            # ... Generate H_i
            n_vars = mdata[mod].var['highly_variable'].sum()
            self.H[mod] = torch.rand(n_vars, self.latent_dim, device=device, dtype=dtype)
            self.H[mod] /= self.H[mod].sum(0)

            # ... Generate G_{H_i}
            self.GH[mod] = torch.rand(n_vars, mdata[mod].n_obs, requires_grad=True, device=device, dtype=dtype)

            # ... Generate G_{W_i}
            self.GW[mod] = torch.rand(n_vars, mdata[mod].n_obs, requires_grad=True, device=device, dtype=dtype)

        # Generate W
        self.W = torch.rand(self.latent_dim, mdata.n_obs, device=device, dtype=dtype)
        self.W /= self.W.sum(0)

        self.optimize(modalities=mdata.mod, n_iter_inner=n_iter_inner, n_iter=n_iter, device=device, K=K)

        for mod in mdata.mod:
            mdata[mod].uns['H_OT'] = self.H[mod]
        mdata.obsm['W_OT'] = self.W.T
