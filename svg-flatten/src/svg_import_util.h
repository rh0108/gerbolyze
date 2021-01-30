/*
 * This file is part of gerbolyze, a vector image preprocessing toolchain 
 * Copyright (C) 2021 Jan Sebastian Götte <gerbolyze@jaseg.de>
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 * 
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#pragma once

#include <math.h>
#include <cmath>
#include <stdlib.h>
#include <assert.h>
#include <limits>
#include <vector>
#include <string>
#include <iostream>
#include <sstream>
#include <regex>

#include <pango/pangocairo.h>
#include <cairo-svg.h>

#include <clipper.hpp>
#include "cairo_clipper.hpp"

#include <pugixml.hpp>

#include "svg_import_defs.h"

namespace gerbolyze {

/* Coordinate system selection for things like "patternContentUnits" */
enum RelativeUnits {
    SVG_UnknownUnits = 0,
    SVG_UserSpaceOnUse,
    SVG_ObjectBoundingBox,
};

void print_matrix(cairo_t *cr, bool print_examples=false);
double usvg_double_attr(const pugi::xml_node &node, const char *attr, double default_value=0.0);
std::string usvg_id_url(std::string attr);
RelativeUnits map_str_to_units(std::string str, RelativeUnits default_val=SVG_UnknownUnits);
void load_cairo_matrix_from_svg(const std::string &transform, cairo_matrix_t &mat);
void apply_cairo_transform_from_svg(cairo_t *cr, const std::string &transform);
std::string parse_data_iri(const std::string &data_url);
void apply_viewport_matrix(cairo_t *cr, cairo_matrix_t &viewport_matrix);

} /* namespace gerbolyze */

