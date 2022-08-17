# test the synchrotron module
import numpy as np
import astropy.units as u
from astropy.constants import m_e
from astropy.coordinates import Distance
import pytest
import shutil
from pathlib import Path
from agnpy.emission_regions import Blob
from agnpy.spectra import PowerLaw, LogParabola, BrokenPowerLaw
from agnpy.synchrotron import Synchrotron, nu_synch_peak
from agnpy.utils.math import trapz_loglog
from .utils import (
    make_comparison_plot,
    extract_columns_sample_file,
    check_deviation,
)

agnpy_dir = Path(__file__).parent.parent
# where to read sampled files
data_dir = agnpy_dir / "data"
# where to save figures, clean-up before making the new
figures_dir = Path(agnpy_dir.parent / "crosschecks/figures/synchrotron")
if figures_dir.exists() and figures_dir.is_dir():
    shutil.rmtree(figures_dir)
figures_dir.mkdir(parents=True, exist_ok=True)

# definition of the blobs
# as a default we use the same parameters of Figure 7.4 in Dermer Menon 2009
W_e = 1e48 * u.Unit("erg")
R_b = 1e16 * u.cm
V_b = 4 / 3 * np.pi * R_b ** 3
PWL = PowerLaw.from_total_energy(W_e, V_b, m_e, p=2.8, gamma_min=1e2, gamma_max=1e5)
LP = LogParabola.from_total_energy(
    W_e, V_b, m_e, p=2.8, q=0.2, gamma_0=1e3, gamma_min=1e2, gamma_max=1e5
)

PWL_BLOB = Blob(
    R_b=R_b, z=Distance(1e27, unit=u.cm).z, delta_D=10, Gamma=10, B=1 * u.G, n_e=PWL
)

LP_BLOB = Blob(
    R_b=R_b, z=Distance(1e27, unit=u.cm).z, delta_D=10, Gamma=10, B=1 * u.G, n_e=LP
)


class TestSynchrotron:
    """Class grouping all tests related to the Synchrotron class."""

    @pytest.mark.parametrize("gamma_max, nu_range_max", [("1e5", 1e18), ("1e7", 1e22)])
    def test_synch_reference_sed(self, gamma_max, nu_range_max):
        """Test agnpy synchrotron SED against the ones in Figure 7.4 of Dermer
        Menon 2009."""

        # reference SED
        nu_ref, sed_ref = extract_columns_sample_file(
            f"{data_dir}/reference_seds/dermer_menon_2009/figure_7_4/synchrotron_gamma_max_{gamma_max}.txt",
            "Hz",
            "erg cm-2 s-1",
        )

        # agnpy
        PWL_BLOB.n_e.gamma_max = float(gamma_max)
        PWL_BLOB.set_gamma_e(gamma_size=200, gamma_max=float(gamma_max))
        synch = Synchrotron(PWL_BLOB)
        sed_agnpy = synch.sed_flux(nu_ref)

        # sed comparison plot
        nu_range = [1e10, nu_range_max] * u.Hz
        make_comparison_plot(
            nu_ref,
            sed_agnpy,
            sed_ref,
            "agnpy",
            "Figure 7.4, Dermer and Menon (2009)",
            "Synchrotron, " + r"$\gamma_{max} = $" + gamma_max,
            f"{figures_dir}/synch_comparison_gamma_max_{gamma_max}_figure_7_4_dermer_menon_2009.png",
            "sed",
            y_range=[1e-13, 1e-9],
            comparison_range=nu_range.to_value("Hz"),
        )
        # requires that the SED points deviate less than 25% from the figure
        assert check_deviation(nu_ref, sed_agnpy, sed_ref, 0.25, nu_range)

    @pytest.mark.parametrize(
        "file_ref , n_e, figure_title, figure_path",
        [
            (
                f"{data_dir}/reference_seds/jetset/data/synch_ssa_pwl_jetset_1.1.2.txt",
                PowerLaw.from_total_density(
                    n_tot=1e2 * u.Unit("cm-3"),
                    mass=m_e,
                    p=2,
                    gamma_min=2,
                    gamma_max=1e6,
                ),
                "Self-Absorbed Synchrotron, power-law electron distribution",
                f"{figures_dir}/ssa_pwl_comparison_jetset_1.1.2.png",
            ),
            (
                f"{data_dir}/reference_seds/jetset/data/synch_ssa_bpwl_jetset_1.1.2.txt",
                BrokenPowerLaw.from_total_density(
                    n_tot=1e2 * u.Unit("cm-3"),
                    mass=m_e,
                    p1=2,
                    p2=3,
                    gamma_b=1e4,
                    gamma_min=2,
                    gamma_max=1e6,
                ),
                "Self-Absorbed Synchrotron, broken power-law electron distribution",
                f"{figures_dir}/ssa_bpwl_comparison_jetset_1.1.2.png",
            ),
            (
                f"{data_dir}/reference_seds/jetset/data/synch_ssa_lp_jetset_1.1.2.txt",
                LogParabola.from_total_density(
                    n_tot=1e2 * u.Unit("cm-3"),
                    mass=m_e,
                    p=2,
                    q=0.4,
                    gamma_0=1e4,
                    gamma_min=2,
                    gamma_max=1e6,
                ),
                "Self-Absorbed Synchrotron, log-parabola electron distribution",
                f"{figures_dir}/ssa_lp_comparison_jetset_1.1.2.png",
            ),
        ],
    )
    def test_ssa_reference_sed(
        self, file_ref, n_e, figure_title, figure_path,
    ):
        """Test SSA SED generated by a given electron distribution against the
        ones generated with jetset version 1.1.2, via jetset_ssa_sed.py script."""
        # reference SED
        nu_ref, sed_ref = extract_columns_sample_file(file_ref, "Hz", "erg cm-2 s-1")

        # same parameters used to produce the jetset SED
        blob = Blob(R_b=5e15 * u.cm, z=0.1, delta_D=10, Gamma=10, B=0.1 * u.G, n_e=n_e)

        # recompute the SED at the same ordinates where the figure was sampled
        ssa = Synchrotron(blob, ssa=True)
        sed_agnpy = ssa.sed_flux(nu_ref)

        # sed comparison plot, we will check between 10^(11) and 10^(19) Hz
        nu_range = [1e11, 1e19] * u.Hz
        make_comparison_plot(
            nu_ref,
            sed_agnpy,
            sed_ref,
            "agnpy",
            "jetset 1.1.2",
            figure_title,
            figure_path,
            "sed",
            comparison_range=nu_range.to_value("Hz"),
        )
        # requires that the SED points deviate less than 5% from the figure
        assert check_deviation(nu_ref, sed_agnpy, sed_ref, 0.05, nu_range)

    def test_synch_delta_sed(self):
        """Check that in a given frequency range the full synchrotron SED coincides
        with the delta function approximation."""
        nu = np.logspace(10, 20) * u.Hz
        synch = Synchrotron(LP_BLOB)
        sed_full = synch.sed_flux(nu)
        sed_delta = synch.sed_flux_delta_approx(nu)

        # range of comparison
        nu_range = [1e12, 1e17] * u.Hz
        make_comparison_plot(
            nu,
            sed_delta,
            sed_full,
            "delta function approximation",
            "full integration",
            "Synchrotron",
            f"{figures_dir}/synch_comparison_delta_aprproximation.png",
            "sed",
            [1e-16, 1e-8],
            nu_range.to_value("Hz"),
        )

        # requires that the delta approximation SED points deviate less than 10%
        assert check_deviation(nu, sed_delta, sed_full, 0.1, nu_range)

    def test_sed_integration_methods(self):
        """Test different integration methods against each other:
        simple trapezoidal rule vs trapezoidal rule in log-log space.
        """
        nu = np.logspace(8, 22) * u.Hz
        synch_trapz = Synchrotron(PWL_BLOB, integrator=np.trapz)
        synch_trapz_loglog = Synchrotron(PWL_BLOB, integrator=trapz_loglog)
        sed_synch_trapz = synch_trapz.sed_flux(nu)
        sed_synch_trapz_loglog = synch_trapz_loglog.sed_flux(nu)

        make_comparison_plot(
            nu,
            sed_synch_trapz_loglog,
            sed_synch_trapz,
            "trapezoidal log-log integration",
            "trapezoidal integration",
            "Synchrotron",
            f"{figures_dir}/synch_comparison_integration_methods.png",
            "sed",
        )

        # requires that the SED points deviate less than 10%
        assert check_deviation(nu, sed_synch_trapz_loglog, sed_synch_trapz, 0.1)

    def test_nu_synch_peak(self):
        """Test peak synchrotron frequency for a given magnetic field and Lorentz factor."""
        gamma = 100
        nu_synch = nu_synch_peak(PWL_BLOB.B, gamma).to_value("Hz")
        assert np.isclose(nu_synch, 27992489872.33304, atol=0)
