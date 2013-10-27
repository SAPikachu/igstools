igstools
========

Tools for parsing bluray IGS menus

Parser and decoder are ported from `two <http://patches.libav.org/patch/22446/>`_ `libav patches <http://patches.libav.org/patch/22445/>`_. Credits to `David Girault <mailto:david@dhgirault.fr>`_.


Installation
------------

Python 3.3 or later is required.

Using `pip <http://www.pip-installer.org/en/latest/>`_ to install is recommended::

    pip install https://github.com/SAPikachu/igstools/archive/master.zip

Alternatively, you can also clone this repository, and run::

    setup.py install

You need to manually install `pypng <https://github.com/drj11/pypng>`_ if you use this method though.


Usage
-----

Currently, only 1 tool is available: ``igstopng``

To use it, first use `BDedit <http://www.videohelp.com/tools/BDedit>`_ to extract IGS menu file (\*.mnu) from your M2TS file, then run::

    igstopng your.mnu

Note: As of 0.9.3, ``igstopng`` supports directly exporting from M2TS file.
The speed is slower, but sometimes ``BDedit`` exports corrupted menu file and you may get correct result from direct export.

All menu pages will be exported alongside the menu file. For every page, 6 states (normal/selected/activated multiplied with start/stop) of buttons will be exported to 6 different page images. (This may be changed in the future since it is rather messed up and unnecessary)

Note: If the command above doesn't work on Windows, try this::

    py -3 -migstools your.mnu


Known issues
------------

The tool is very slow, it may take 3 ~ 5 seconds to extract a single menu page. If someone finds it useful I may try to optimize it...
