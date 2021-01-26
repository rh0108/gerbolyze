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

#include <cmath>
#include <algorithm>
#include <string>
#include <iostream>
#include <iomanip>
#include <gerbolyze.hpp>
#include <svg_import_defs.h>
#include <svg_geom.h>
#include "polylinecombine.hpp"

using namespace gerbolyze;
using namespace std;

static void polygon_to_cavc (const Polygon &in, cavc::Polyline<double> &out) {
    for (auto &p : in) {
        out.addVertex(p[0], p[1], 0);
    }
    out.isClosed() = true; /* sic! */
}

static void cavc_to_polygon (const cavc::Polyline<double> &in, Polygon &out) {
    for (auto &p : in.vertexes()) {
        out.emplace_back(d2p{p.x(), p.y()});
    }
}

namespace gerbolyze {
    class Flattener_D {
    public:
        vector<cavc::Polyline<double>> dark_polys;

        void add_dark_polygon(const Polygon &in) {
            polygon_to_cavc(in, dark_polys.emplace_back());
        }
    };
}

Flattener::Flattener(PolygonSink &sink) : m_sink(sink) {
    d = new Flattener_D();
}

Flattener::~Flattener() {
    delete d;
}

void Flattener::header(d2p origin, d2p size) {
    m_sink.header(origin, size);
}



Flattener &Flattener::operator<<(GerberPolarityToken pol) {
    if (m_current_polarity != pol) {
        m_current_polarity = pol;
    }

    return *this;
}

Flattener &Flattener::operator<<(const Polygon &poly) {
    static int i=0, j=0;

    if (m_current_polarity == GRB_POL_DARK) {
        d->add_dark_polygon(poly);
        cerr << "dark primitive " << i++ << endl;
    } else { /* clear */
        cerr << "clear primitive " << j++ << endl;

        cavc::Polyline<double> sub;
        polygon_to_cavc (poly, sub);

        vector<cavc::Polyline<double>> new_dark_polys;
        new_dark_polys.reserve(d->dark_polys.size());

        for (cavc::Polyline<double> cavc_in : d->dark_polys) {
            auto res = cavc::combinePolylines(cavc_in, sub, cavc::PlineCombineMode::Exclude);

            if (res.subtracted.size() == 0) {
                for (auto &rem : res.remaining) {
                    new_dark_polys.push_back(std::move(rem));
                }

            } else {
                assert (res.remaining.size() == 1);
                assert (res.subtracted.size() == 1);

                auto &rem = res.remaining[0];
                auto &sub = res.subtracted[0];
                auto bbox = getExtents(rem);

                cavc::Polyline<double> quad;
                quad.addVertex(bbox.xMin, bbox.yMin, 0);
                if (sub.vertexes()[0].x() < sub.vertexes()[1].x()) {
                    quad.addVertex(sub.vertexes()[0]);
                    quad.addVertex(sub.vertexes()[1]);
                } else {
                    quad.addVertex(sub.vertexes()[1]);
                    quad.addVertex(sub.vertexes()[0]);
                }
                quad.addVertex(bbox.xMax, bbox.yMin, 0);
                quad.isClosed() = true; /* sic! */

                auto res2 = cavc::combinePolylines(rem, quad, cavc::PlineCombineMode::Exclude);
                assert (res2.subtracted.size() == 0);

                for (auto &rem : res2.remaining) {
                    auto res3 = cavc::combinePolylines(rem, sub, cavc::PlineCombineMode::Exclude);
                    assert (res3.subtracted.size() == 0);
                    for (auto &p : res3.remaining) {
                        new_dark_polys.push_back(std::move(p));
                    }
                }

                auto res4 = cavc::combinePolylines(rem, quad, cavc::PlineCombineMode::Intersect);
                assert (res4.subtracted.size() == 0);

                for (auto &rem : res4.remaining) {
                    auto res5 = cavc::combinePolylines(rem, sub, cavc::PlineCombineMode::Exclude);
                    assert (res5.subtracted.size() == 0);
                    for (auto &p : res5.remaining) {
                        new_dark_polys.push_back(std::move(p));
                    }
                }
            }
        }

        d->dark_polys = std::move(new_dark_polys);
    }

    return *this;
}

void Flattener::footer() {
    m_sink << GRB_POL_DARK;

    for (auto &poly : d->dark_polys) {
        Polygon poly_out;
        for (auto &p : poly.vertexes()) {
            poly_out.emplace_back(d2p{p.x(), p.y()});
        }
        m_sink << poly_out;
    }

    m_sink.footer();
}

