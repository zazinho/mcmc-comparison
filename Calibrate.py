### In this script we develop a procedure that return a list or a file containing
## all the metrics and information to assess a MCMC algorithm given a compartmental model 

from estival.model import BayesianCompartmentalModel
import pymc as pm
import pandas as pd
from estival.wrappers import pymc as epm
import arviz as az #For convergence stats and diagnostics
from arviz import InferenceData
import time
import matplotlib .pyplot as plt

import numpyro
from numpyro import distributions as dist
from numpyro import infer
from jax import random

def compute_max_Rhat(
        idata: InferenceData
        
) -> float:
    Rhat = az.rhat(idata).variables
    # Extract data from the Frozen object
    data = {key: value.values.item() for key, value in Rhat.items()}

    # Create DataFrame from the extracted data
    max_rhat_df = pd.DataFrame(data, index=[0])
    return max_rhat_df.values.max()
#_________________________________________________________

def compute_mean_Rhat(
        idata: InferenceData
        
) -> float:
    Rhat = az.rhat(idata).variables
    # Extract data from the Frozen object
    data = {key: value.values.item() for key, value in Rhat.items()}

    # Create DataFrame from the extracted data
    mean_rhat_df = pd.DataFrame(data, index=[0])
    return mean_rhat_df.values.mean()

#__________________________________________________________
def compute_mean_Ess(
        idata: InferenceData
        
) -> float:
    Ess = az.ess(idata).variables
    # Extract data from the Frozen object
    data = {key: value.values.item() for key, value in Ess.items()}

    # Create DataFrame from the extracted data
    mean_ess_df = pd.DataFrame(data, index=[0])
    return mean_ess_df.values.mean()

#_____________________________________________________________
def compute_min_Ess(
        idata: InferenceData
        
) -> float:
    Ess = az.ess(idata).variables
    # Extract data from the Frozen object
    data = {key: value.values.item() for key, value in Ess.items()}

    # Create DataFrame from the extracted data
    min_ess_df = pd.DataFrame(data, index=[0])
    return min_ess_df.values.min()
    
    

def Sampling_calib(
        bcm_model : BayesianCompartmentalModel,
        mcmc_algo: str,
        initial_params: dict,
        draws = 1000,
        tune=100,
        chains = 1,
        cores = 1,
        # hmc_warmup = 1000,
                ) -> list[InferenceData, float] :

    """
    Args:
    - model : A BayesianCompartmentalModel, within wich the targets and priors distributions will be extracted.
    - mcmc algo (str) : A Markov Chain Monte Carlo algorithm can be from the Pymc/Numpyro list of MCMC algorithms or a disigned sampler algorithm.
                  please refer do the Pymc documentation for more details.
    - initial_params (dict) : The MCMC algorithm starting points.
    - draws(int) : The size of the chains (each chain if running multiple chains). Default 1000 samples.
    - tune (int, default 100): Number of tune for Pymc MCMC algo, number of warmup for HMC family 
    - chains(int, default 1): Number of chains for multiple chains sampling
    -cores(int, default 1 ): Number of cpu cores to use for mutlichain sampling.

    Returns:
     - An arviz InferenceData which provides the stats and diagnostics of the chains convergence.
     We may add soon the ESS/second, the minimum number of iterations to obtain the given Ess etc..
    """
    sampler_name = mcmc_algo.__name__ #Name of the sampler
    if sampler_name == "NUTS": # We need to set some specifications for this sampler. 
                               # Use of numpyro and/or BlackJax 
        # pass
        def nmodel():
            sampled = {k:numpyro.sample(k, dist.Uniform(0.0,1.0)) for k in bcm_model.parameters}
            ll = numpyro.factor("ll", bcm_model.loglikelihood(**sampled))

        kernel = infer.NUTS(nmodel)
        mcmc = infer.MCMC(kernel, num_warmup=tune, num_chains=4, num_samples=draws, progress_bar=False)
        start = time.time()

        mcmc.run(random.PRNGKey(0))
        end = time.time()
        Time = end - start
        idata = az.from_numpyro(mcmc)

    else :
        with pm.Model() as model:

            # This is all you need - a single call to use_model
            variables = epm.use_model(bcm_model)

            # Now call a sampler using the variables from use_model
            # In this case we use the Differential Evolution Metropolis sampler
            # See the PyMC docs for more details
            step_kwargs = {} #dict(variables,proposal_dist = pm.NormalProposal)
            step = mcmc_algo(**step_kwargs)
            start = time.time()
            idata = pm.sample(step= step,
                                initvals = initial_params,
                                draws=draws,
                                tune = tune ,
                                cores=cores,
                                chains=chains,
                                progressbar=False
                                )   
            end = time.time()
            Time = end - start

    return idata, Time # Will use arviz to examine outputs

def Compute_metrics(
        mcmc_algo: str,
        idata: InferenceData,
        Time: float,
        draws, 
        chains,
        tune,
                    ) :
    
    ess_mean = compute_mean_Ess(idata)
    ess_min = compute_min_Ess(idata)

    rhat_mean = compute_mean_Rhat(idata)
    rhat_max = compute_max_Rhat(idata)

    results = dict(
        Sampler = mcmc_algo.__name__,
        Draws = draws,
        Chains = chains,
        Tune = tune,
        Time = Time,
        Mean_ESS = ess_mean,
        Min_Ess = ess_min,
        Ess_per_sec = ess_mean/Time, 
        Mean_Rhat = rhat_mean,
        Rhat_max = rhat_max,

        Trace = [idata],
    )
    
    return pd.DataFrame(results)

def plot_comparison_bars(results_df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2) #, figsize=(20, 12))
    ax = axes[0]
    ax.bar(x=results_df["Run"], height=results_df["Ess_per_sec"])#, legend=False)
    ax.set_title("ESS per Second")
    ax.set_xlabel("")
    labels = ax.get_xticklabels()
    """
    ax = axes[1]
    results_df.plot.bar(y="ESS_pct", x="Run", ax=ax, legend=False)
    ax.set_title("ESS Percentage")
    ax.set_xlabel("")
    labels = ax.get_xticklabels()
    """
    ax = axes[1]
    ax.bar(x=results_df["Run"], height=results_df["Mean_Rhat"])#, legend=False)
    ax.set_title(r"$\hat{R}$")
    ax.set_xlabel("")
    ax.set_ylim(1)
    labels = ax.get_xticklabels()
    plt.suptitle(f"Comparison of Runs for ... Target Distribution", fontsize=16)

    plt.tight_layout()
    plt.show()