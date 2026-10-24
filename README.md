# paired-power

A pure-Python command-line calculator for paired-sample t-test power. It uses only the Python standard library.

## Install and run

Requires Python 3.10 or newer; no package installation or third-party dependencies are needed. From this directory:

```powershell
python --version
python gpower_clone.py --test t-paired --mode a-priori --tails 1 --dz 0.5 --alpha 0.05 --power 0.95
python gpower_clone.py --test t-paired --mode post-hoc --tails 2 --dz 0.5 --alpha 0.05 --n_total 45
python gpower_clone.py --test t-paired --mode compromise --tails 1 --dz 0.5 --beta_alpha_ratio 1 --n_total 45
python gpower_clone.py --version
```

On Windows, `gpower-clone.cmd` forwards arguments to `gpower_clone.py`, so you can run `gpower-clone --version` after adding this directory to `PATH`.

For this educational, non-commercial course exercise, calculations are independently implemented from statistical definitions and observed behavior. This project is not G*Power, is not endorsed by its authors, and does not include its binary or decompiled output.

The command prints one JSON line. `paired_power.py` exposes the reusable calculation engine; `gpower_clone.py` validates arguments, calls the engine, and serializes the result.
