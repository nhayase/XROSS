#!/usr/bin/env python3
"""
build_exe/build.py -- Build XROSS as a standalone Windows executable.

Usage (from project root, in Anaconda Prompt):
    pip install pyinstaller
    python build_exe/build.py --backend pyinstaller --onefile
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "xross", "__main__.py")
DIST = os.path.join(ROOT, "dist")
BUILD_TMP = os.path.join(ROOT, "build_tmp")
SPEC_DIR = os.path.join(ROOT, "build_exe")
ICO = os.path.join(ROOT, "favicon.ico")
UPX_DIR = os.path.join(SPEC_DIR, "upx")

EXCLUDES = [
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_qt5",
    "matplotlib.backends.backend_qt4agg",
    "matplotlib.backends.backend_qt4",
    "matplotlib.backends.backend_webagg",
    "matplotlib.backends.backend_webagg_core",
    "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_gtk3cairo",
    "matplotlib.backends.backend_gtk3",
    "matplotlib.backends.backend_gtk4agg",
    "matplotlib.backends.backend_gtk4cairo",
    "matplotlib.backends.backend_wx",
    "matplotlib.backends.backend_wxagg",
    "matplotlib.backends.backend_wxcairo",
    "matplotlib.backends.backend_nbagg",
    "matplotlib.backends.backend_cairo",
    "matplotlib.backends.backend_macosx",
    "sklearn.datasets",
    "sklearn.feature_extraction",
    "sklearn.semi_supervised",
    "sklearn.cluster",
    "sklearn.manifold",
    "sklearn.neural_network",
    "sklearn.svm",
    "sklearn.gaussian_process",
    "sklearn.naive_bayes",
    "sklearn.neighbors",
    "sklearn.decomposition",
    "sklearn.covariance",
    "sklearn.cross_decomposition",
    "sklearn.discriminant_analysis",
    "sklearn.isotonic",
    "sklearn.kernel_approximation",
    "sklearn.kernel_ridge",
    "sklearn.mixture",
    "sklearn.multiclass",
    "sklearn.multioutput",
    "sklearn.feature_selection",
    "sklearn.impute",
    "sklearn.compose",
    "sklearn.pipeline",
    "sklearn.calibration",
    "optuna.visualization",
    "optuna.integration",
    "plotly", "bokeh", "IPython", "notebook", "jupyter",
    "sphinx", "pytest", "PIL", "cv2", "torch", "tensorflow",
    "h5py", "tables", "sqlalchemy", "sympy", "docutils",
]

HIDDEN_IMPORTS = [
    "sklearn.ensemble._forest",
    "sklearn.ensemble._gb",
    "sklearn.linear_model._bayes",
    "sklearn.utils._typedefs",
    "sklearn.utils._heap",
    "sklearn.utils._sorting",
    "sklearn.utils._vector_sentinel",
    "sklearn.neighbors._partition_nodes",
    "matplotlib.backends.backend_tkagg",
]


def write_spec(onefile):
    """Write XROSS.spec file and return its path."""
    lines = []
    lines.append("# -*- mode: python ; coding: utf-8 -*-")
    lines.append("")
    lines.append("a = Analysis(")
    lines.append("    [r'" + ENTRY + "'],")
    lines.append("    pathex=[r'" + ROOT + "'],")
    lines.append("    binaries=[],")

    # datas
    lines.append("    datas=[")
    for d in ["geo", "nk", "xrdml", "save"]:
        src = os.path.join(ROOT, d)
        if os.path.isdir(src):
            lines.append("        (r'" + src + "', '" + d + "'),")
    lines.append("    ],")

    # hiddenimports
    lines.append("    hiddenimports=[")
    for h in HIDDEN_IMPORTS:
        lines.append("        '" + h + "',")
    lines.append("    ],")

    lines.append("    hookspath=[],")
    lines.append("    hooksconfig={},")
    lines.append("    runtime_hooks=[],")

    # excludes
    lines.append("    excludes=[")
    for e in EXCLUDES:
        lines.append("        '" + e + "',")
    lines.append("    ],")

    lines.append("    noarchive=False,")
    lines.append(")")
    lines.append("")
    lines.append("pyz = PYZ(a.pure)")
    lines.append("")

    # EXE block
    if onefile:
        lines.append("exe = EXE(")
        lines.append("    pyz,")
        lines.append("    a.scripts,")
        lines.append("    a.binaries,")
        lines.append("    a.datas,")
        lines.append("    name='XROSS',")
        lines.append("    debug=False,")
        lines.append("    strip=False,")
        lines.append("    upx=True,")
        if os.path.isdir(UPX_DIR):
            lines.append("    upx_dir=r'" + UPX_DIR + "',")
        lines.append("    console=False,")
        if os.path.exists(ICO):
            lines.append("    icon=r'" + ICO + "',")
        lines.append(")")
    else:
        lines.append("exe = EXE(")
        lines.append("    pyz,")
        lines.append("    a.scripts,")
        lines.append("    exclude_binaries=True,")
        lines.append("    name='XROSS',")
        lines.append("    debug=False,")
        lines.append("    strip=False,")
        lines.append("    upx=True,")
        if os.path.isdir(UPX_DIR):
            lines.append("    upx_dir=r'" + UPX_DIR + "',")
        lines.append("    console=False,")
        if os.path.exists(ICO):
            lines.append("    icon=r'" + ICO + "',")
        lines.append(")")
        lines.append("")
        lines.append("coll = COLLECT(")
        lines.append("    exe,")
        lines.append("    a.binaries,")
        lines.append("    a.datas,")
        lines.append("    strip=False,")
        lines.append("    upx=True,")
        lines.append("    name='XROSS',")
        lines.append(")")

    spec_path = os.path.join(SPEC_DIR, "XROSS.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("Generated: " + spec_path)
    return spec_path


def build_pyinstaller(onefile):
    """Build with PyInstaller."""
    try:
        import PyInstaller
        print("PyInstaller " + PyInstaller.__version__ + " found.")
    except ImportError:
        print("ERROR: PyInstaller not found.")
        print("  pip install pyinstaller")
        sys.exit(1)

    spec_path = write_spec(onefile)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--distpath=" + DIST,
        "--workpath=" + BUILD_TMP,
        spec_path,
    ]
    print("")
    print("Running: " + " ".join(cmd))
    print("")
    subprocess.run(cmd, check=True)

    # Report
    if onefile:
        exe = os.path.join(DIST, "XROSS.exe")
        if os.path.exists(exe):
            mb = os.path.getsize(exe) / (1024 * 1024)
            print("")
            print("SUCCESS: " + exe + "  (" + str(int(mb)) + " MB)")
    else:
        folder = os.path.join(DIST, "XROSS")
        if os.path.isdir(folder):
            total = sum(
                os.path.getsize(os.path.join(dp, fn))
                for dp, _, fns in os.walk(folder) for fn in fns
            )
            mb = total / (1024 * 1024)
            print("")
            print("SUCCESS: " + folder + "  (" + str(int(mb)) + " MB)")


def build_nuitka(onefile):
    """Build with Nuitka."""
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=tk-inter",
        "--enable-plugin=numpy",
        "--include-package=xross",
        "--include-package=sklearn.ensemble",
        "--include-package=sklearn.linear_model",
        "--include-package=sklearn.preprocessing",
        "--include-package=sklearn.model_selection",
        "--include-package=sklearn.inspection",
        "--include-package=sklearn.metrics",
        "--include-package=sklearn.tree",
        "--include-package=sklearn.utils",
        "--output-dir=" + DIST,
        "--windows-console-mode=disable",
    ]
    if onefile:
        cmd.append("--onefile")
    if os.path.exists(ICO):
        cmd.append("--windows-icon-from-ico=" + ICO)
    for mod in EXCLUDES:
        cmd.append("--nofollow-import-to=" + mod)
    cmd.append(ENTRY)

    print("Running: " + " ".join(cmd))
    print("(Nuitka may take 10-30 minutes)")
    subprocess.run(cmd, check=True)
    print("")
    print("Nuitka build complete. Output in " + DIST)


def main():
    parser = argparse.ArgumentParser(description="Build XROSS executable")
    parser.add_argument("--backend", choices=["pyinstaller", "nuitka"],
                        default="pyinstaller")
    parser.add_argument("--onefile", action="store_true")
    args = parser.parse_args()

    print("XROSS exe builder")
    print("  Backend: " + args.backend)
    print("  Mode:    " + ("onefile" if args.onefile else "folder"))
    print("  Root:    " + ROOT)
    print("")

    if args.backend == "nuitka":
        build_nuitka(args.onefile)
    else:
        build_pyinstaller(args.onefile)

    # Cleanup temp
    if os.path.isdir(BUILD_TMP):
        shutil.rmtree(BUILD_TMP, ignore_errors=True)

    print("")
    print("Done.")


if __name__ == "__main__":
    main()
