# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import json

# lamba function to remove leading _ for variable names and return as dict
# based on https://stackoverflow.com/a/31813187
object_dict = lambda o: {key.lstrip('_'): value for key, value in vars(o).items()}
