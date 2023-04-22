from setuptools import setup, find_packages

with open('README.md', 'r') as f:
  long_description = f.read()

setup(
  name='stormcatchments',
  version='0.4.0',
  description='Stormwater network aware catchment delineation',
  long_description=long_description,
  long_description_content_type='text/markdown',
  author='Thomas Ott',    
  author_email='tommy.ott617@gmail.com',
  license='GPLv3',
  url='https://github.com/t-ott/stormcatchments',
  packages=find_packages(
    include=['stormcatchments', 'stormcatchments.*'],
    exclude=['tests']
  ),
  install_requires=[
    'geopandas',
    'networkx',
    'pysheds',
    'rtree'
  ],
  extras_require={
    'basemap': 'contextily',
    'dev': [
      'pytest'
    ],
    'plotting': 'matplotlib'
  },
  classifiers=[
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Topic :: Scientific/Engineering :: GIS',
    'Topic :: Scientific/Engineering :: Hydrology'
  ],
  python_requires='>=3.8'
)
