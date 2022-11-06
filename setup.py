from setuptools import setup, find_packages

with open('README.md', 'r') as f:
  long_description = f.read()

setup(
  name='stormcatchments',
  version='0.1.2',
  description='Stormwater network aware catchment delineation',
  long_description=long_description,
  long_description_content_type='text/markdown',
  author='Thomas Ott',
  author_email='tommy.ott617@gmail.com',
  license='MIT',
  url='https://github.com/t-ott/stormcatchments',
  py_modules=[
    'stormcatchments'
  ],
  packages=find_packages(),
  install_requires=[
    'geopandas',
    'networkx',
    'pysheds',
    'rtree'
  ],
  extra_requires={
    'basemap': 'contextily',
    'dev': [
      'pytest'
    ],
    'plotting': 'matplotlib'
  },
  classifiers=[
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.9',
    'Topic :: Scientific/Engineering :: GIS',
    'Topic :: Scientific/Engineering :: Hydrology'
  ]
)
