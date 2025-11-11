from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="stormcatchments",
    version="0.4.1",
    description="Stormwater network aware catchment delineation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Thomas Ott",
    author_email="68197166+t-ott@users.noreply.github.com",
    license="GPLv3",
    url="https://github.com/t-ott/stormcatchments",
    packages=find_packages(
        include=["stormcatchments", "stormcatchments.*"], exclude=["tests"]
    ),
    install_requires=["geopandas", "networkx", "pysheds", "rtree"],
    extras_require={
        "dev": ["ruff", "pytest"],
        "map": ["contextily", "matplotlib"],
        "util": ["rasterio"],
    },
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Scientific/Engineering :: Hydrology",
    ],
    # TODO: Enforce this?
    # python_requires=">=3.10",
)
