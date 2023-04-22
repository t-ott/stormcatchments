.. stormcatchments documentation master file, created by
   sphinx-quickstart on Tue Jan 31 07:44:23 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to stormcatchments' documentation!
===========================================

Stormwater network aware catchment delineation
----------------------------------------------

Converts existing stormwater infrastucture GIS feature data (points and lines) into a
``networkx`` directed graph (``DiGraph``) object, then utilizes the ``DiGraph`` to
incorporate subsurface flows into urban stormwater catchment delineation. Delineation
functionality is powered by ``pysheds``.

.. toctree::
   :maxdepth: 2
   :caption: Classes:

   network
   delineate

.. toctree::
   :maxdepth: 2
   :caption: Modules:

   stormcatchments

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
