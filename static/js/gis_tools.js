/**
 * GIS Tools — QGIS topology rules, data cleaning, dashboard & map highlights
 */
(function (global) {
    'use strict';

    var ISSUE_STYLES = {
        overlap:       { color: '#e53935', fillColor: '#ef5350', label: 'Must not overlap' },
        gap:           { color: '#ff9800', fillColor: '#ffb74d', label: 'Must not have gaps' },
        invalid:       { color: '#9c27b0', fillColor: '#ba68c8', label: 'Invalid geometry' },
        self_intersect:{ color: '#d32f2f', fillColor: '#e57373', label: 'Must not self-intersect' },
        duplicate:     { color: '#795548', fillColor: '#a1887f', label: 'Must not duplicate' },
        sliver:        { color: '#607d8b', fillColor: '#90a4ae', label: 'Sliver polygon' },
        dangle:        { color: '#f57c00', fillColor: '#ffcc80', label: 'Dangling edge' },
        hole:          { color: '#5c6bc0', fillColor: '#9fa8da', label: 'Invalid hole' },
        null_geom:     { color: '#424242', fillColor: '#757575', label: 'Null / empty geometry' },
        cleaned:       { color: '#00897b', fillColor: '#4db6ac', label: 'Iliyosafishwa' },
        fixed_overlap: { color: '#43a047', fillColor: '#81c784', label: 'Overlap iliyorekebishwa' },
        fixed_gap:     { color: '#1e88e5', fillColor: '#64b5f6', label: 'Gap iliyorekebishwa' }
    };

    var QGIS_RULES = [
        { id: 'must_not_overlap',      label: 'Must not overlap (QGIS)',           key: 'overlap' },
        { id: 'must_not_have_gaps',    label: 'Must not have gaps (QGIS)',         key: 'gap' },
        { id: 'must_be_valid',         label: 'Must not have invalid geometries',  key: 'invalid' },
        { id: 'must_not_self_intersect', label: 'Must not self-intersect (QGIS)', key: 'self_intersect' },
        { id: 'must_not_duplicate',    label: 'Must not duplicate geometries',     key: 'duplicate' },
        { id: 'min_area',              label: 'Must not have sliver polygons',     key: 'sliver' },
        { id: 'must_not_dangle',       label: 'Must not have dangles (QGIS)',      key: 'dangle' },
        { id: 'must_not_have_holes',   label: 'Must not have invalid holes',       key: 'hole' }
    ];

    function featName(f, idx) {
        if (!f || !f.properties) return 'Feature ' + idx;
        return f.properties.name || f.properties.NAME || f.properties.district_n ||
            f.properties.ward_name || ('Feature ' + idx);
    }

    function safeFeature(f, idx) {
        try {
            if (!f || !f.geometry) return null;
            return turf.feature(f.geometry, Object.assign({ _idx: idx }, f.properties || {}));
        } catch (e) {
            return null;
        }
    }

    function isValidGeometry(f) {
        if (!f || !f.geometry) return false;
        try {
            if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') {
                turf.area(f);
                return true;
            }
            if (f.geometry.type === 'LineString' || f.geometry.type === 'MultiLineString') {
                turf.length(f, { units: 'kilometers' });
                return true;
            }
            if (f.geometry.type === 'Point') return true;
        } catch (e) { return false; }
        return false;
    }

    function closeRing(ring) {
        if (!ring || ring.length < 3) return ring;
        var first = ring[0], last = ring[ring.length - 1];
        if (first[0] !== last[0] || first[1] !== last[1]) {
            return ring.concat([[first[0], first[1]]]);
        }
        return ring;
    }

    function runQgisTopology(features, enabledRules, minAreaSqM) {
        minAreaSqM = minAreaSqM || 100;
        var issues = [];
        var stats = { overlap: 0, gap: 0, invalid: 0, self_intersect: 0, duplicate: 0, sliver: 0, dangle: 0, hole: 0, null_geom: 0 };
        var safe = [];
        var geomKeys = {};

        features.forEach(function (raw, idx) {
            if (!raw.geometry) {
                if (enabledRules.null_geom) {
                    stats.null_geom++;
                    issues.push({ rule: 'null_geom', type: 'null_geom', name: featName(raw, idx), feature: raw, message: 'Geometry haipo' });
                }
                return;
            }

            if (enabledRules.invalid && !isValidGeometry(raw)) {
                stats.invalid++;
                issues.push({ rule: 'invalid', type: 'invalid', name: featName(raw, idx), feature: raw, message: 'Jiometri batili' });
            }

            var tf = safeFeature(raw, idx);
            if (!tf) return;
            safe.push({ raw: raw, turf: tf, idx: idx });

            if (enabledRules.duplicate) {
                var gkey = JSON.stringify(raw.geometry);
                if (geomKeys[gkey]) {
                    stats.duplicate++;
                    issues.push({
                        rule: 'duplicate', type: 'duplicate', name: featName(raw, idx),
                        feature: raw, message: 'Duplicate ya ' + geomKeys[gkey]
                    });
                } else {
                    geomKeys[gkey] = featName(raw, idx);
                }
            }

            if (enabledRules.self_intersect && (raw.geometry.type === 'Polygon' || raw.geometry.type === 'MultiPolygon')) {
                try {
                    var kinks = turf.kinks(tf);
                    if (kinks.features.length > 0) {
                        stats.self_intersect++;
                        issues.push({
                            rule: 'self_intersect', type: 'self_intersect', name: featName(raw, idx),
                            feature: raw, message: 'Self-intersection pointi ' + kinks.features.length
                        });
                    }
                } catch (e) { /* skip */ }
            }

            if (enabledRules.sliver && (raw.geometry.type === 'Polygon' || raw.geometry.type === 'MultiPolygon')) {
                try {
                    var areaSqM = turf.area(tf);
                    if (areaSqM > 0 && areaSqM < minAreaSqM) {
                        stats.sliver++;
                        issues.push({
                            rule: 'sliver', type: 'sliver', name: featName(raw, idx),
                            feature: raw, message: 'Eneo dogo: ' + areaSqM.toFixed(1) + ' m²'
                        });
                    }
                } catch (e) { /* skip */ }
            }

            if (enabledRules.hole && raw.geometry.type === 'Polygon' && raw.geometry.coordinates.length > 1) {
                raw.geometry.coordinates.slice(1).forEach(function (hole, hi) {
                    if (hole.length < 4) {
                        stats.hole++;
                        issues.push({
                            rule: 'hole', type: 'hole', name: featName(raw, idx),
                            feature: raw, message: 'Tundu batili #' + (hi + 1)
                        });
                    }
                });
            }
        });

        if (enabledRules.overlap) {
            for (var i = 0; i < safe.length; i++) {
                for (var j = i + 1; j < safe.length; j++) {
                    var a = safe[i], b = safe[j];
                    if (a.raw.geometry.type.indexOf('Polygon') === -1 || b.raw.geometry.type.indexOf('Polygon') === -1) continue;
                    try {
                        if (turf.booleanOverlap(a.turf, b.turf) || turf.booleanWithin(a.turf, b.turf) || turf.booleanWithin(b.turf, a.turf)) {
                            var inter = turf.intersect(a.turf, b.turf);
                            if (inter) {
                                stats.overlap++;
                                issues.push({
                                    rule: 'overlap', type: 'overlap',
                                    name: featName(a.raw, a.idx), b: featName(b.raw, b.idx),
                                    feature: { type: 'Feature', properties: { name: 'Overlap' }, geometry: inter.geometry },
                                    message: featName(a.raw, a.idx) + ' / ' + featName(b.raw, b.idx)
                                });
                            }
                        }
                    } catch (e) { /* skip */ }
                }
            }
        }

        if (enabledRules.gap && safe.length > 1) {
            var polys = safe.filter(function (s) { return s.raw.geometry.type.indexOf('Polygon') !== -1; });
            if (polys.length >= 2) {
                try {
                    var collection = turf.featureCollection(polys.map(function (p) { return p.turf; }));
                    var hull = turf.convex(collection);
                    var union = polys[0].turf;
                    for (var u = 1; u < polys.length; u++) {
                        try { union = turf.union(union, polys[u].turf); } catch (e2) { /* skip */ }
                    }
                    if (hull && union) {
                        var gaps = turf.difference(hull, union);
                        if (gaps && turf.area(gaps) > minAreaSqM) {
                            stats.gap++;
                            issues.push({
                                rule: 'gap', type: 'gap', name: 'Pengo la topology',
                                feature: { type: 'Feature', properties: { name: 'Gap' }, geometry: gaps.geometry },
                                message: 'Pengo ~' + turf.area(gaps).toFixed(0) + ' m²'
                            });
                        }
                    }
                } catch (e) { /* skip */ }
            }
        }

        if (enabledRules.dangle) {
            safe.forEach(function (s) {
                if (s.raw.geometry.type !== 'LineString' && s.raw.geometry.type !== 'MultiLineString') return;
                try {
                    var coords = s.raw.geometry.type === 'LineString'
                        ? [s.raw.geometry.coordinates]
                        : s.raw.geometry.coordinates;
                    coords.forEach(function (line) {
                        if (line.length < 2) {
                            stats.dangle++;
                            issues.push({ rule: 'dangle', type: 'dangle', name: featName(s.raw, s.idx), feature: s.raw, message: 'Line fupi / dangle' });
                        }
                    });
                } catch (e) { /* skip */ }
            });
        }

        return { issues: issues, stats: stats, featureCount: features.length };
    }

    function cleanGeoJSON(features, options) {
        options = options || {};
        var report = {
            removed: 0, fixed_invalid: 0, fixed_overlap: 0, fixed_gap: 0,
            fixed_duplicate: 0, fixed_sliver: 0, fixed_coords: 0, issues: []
        };
        var minArea = options.minAreaSqM || 100;
        var out = [];

        features.forEach(function (f, idx) {
            if (!f || !f.geometry) {
                report.removed++;
                report.issues.push({ type: 'null_geom', name: featName(f, idx), message: 'Imeondolewa — hakuna geometry' });
                return;
            }

            var copy = JSON.parse(JSON.stringify(f));

            try {
                if (options.fix_invalid || options.fix_coords) {
                    if (copy.geometry.type === 'Polygon') {
                        copy.geometry.coordinates = copy.geometry.coordinates.map(function (ring) {
                            var closed = closeRing(ring);
                            var line = turf.lineString(closed);
                            var cleaned = turf.cleanCoords(line);
                            report.fixed_coords++;
                            return cleaned.geometry.coordinates;
                        });
                    }
                    var tf = turf.feature(copy.geometry);
                    if (options.fix_invalid && (copy.geometry.type === 'Polygon' || copy.geometry.type === 'MultiPolygon')) {
                        try {
                            var unkinked = turf.unkinkPolygon(tf);
                            if (unkinked.features.length === 1) {
                                copy.geometry = unkinked.features[0].geometry;
                                report.fixed_invalid++;
                            }
                        } catch (e) { /* skip */ }
                    }
                }

                if (options.remove_slivers && (copy.geometry.type === 'Polygon' || copy.geometry.type === 'MultiPolygon')) {
                    var area = turf.area(turf.feature(copy.geometry));
                    if (area < minArea) {
                        report.fixed_sliver++;
                        report.issues.push({ type: 'sliver', name: featName(copy, idx), message: 'Sliver imeondolewa (' + area.toFixed(1) + ' m²)' });
                        return;
                    }
                }

                out.push(copy);
            } catch (e) {
                report.removed++;
                report.issues.push({ type: 'invalid', name: featName(f, idx), message: 'Imeondolewa — batili' });
            }
        });

        if (options.remove_duplicates) {
            var seen = {};
            out = out.filter(function (f) {
                var key = JSON.stringify(f.geometry);
                if (seen[key]) {
                    report.fixed_duplicate++;
                    report.issues.push({ type: 'duplicate', name: featName(f, 0), message: 'Duplicate imeondolewa' });
                    return false;
                }
                seen[key] = true;
                return true;
            });
        }

        if (options.fix_overlaps && out.length > 1) {
            for (var i = 0; i < out.length; i++) {
                for (var j = i + 1; j < out.length; j++) {
                    try {
                        var fa = turf.feature(out[i].geometry);
                        var fb = turf.feature(out[j].geometry);
                        if (turf.booleanOverlap(fa, fb)) {
                            var diff = turf.difference(fb, fa);
                            if (diff) {
                                out[j].geometry = diff.geometry;
                                report.fixed_overlap++;
                                report.issues.push({
                                    type: 'fixed_overlap',
                                    name: featName(out[j], j),
                                    message: 'Overlap imerekebishwa na ' + featName(out[i], i),
                                    feature: out[j]
                                });
                            }
                        }
                    } catch (e) { /* skip */ }
                }
            }
        }

        if (options.fix_gaps && out.length > 1) {
            try {
                var polys = out.filter(function (f) { return f.geometry.type.indexOf('Polygon') !== -1; });
                if (polys.length >= 2) {
                    var union = turf.feature(polys[0].geometry);
                    for (var g = 1; g < polys.length; g++) {
                        try { union = turf.union(union, turf.feature(polys[g].geometry)); } catch (e2) { /* skip */ }
                    }
                    var hull = turf.convex(turf.featureCollection(polys.map(function (p) { return turf.feature(p.geometry); })));
                    if (hull && union) {
                        var gap = turf.difference(hull, union);
                        if (gap && turf.area(gap) > minArea) {
                            var buffered = turf.buffer(gap, 0.00001, { units: 'degrees' });
                            if (buffered) {
                                out.push({ type: 'Feature', properties: { name: 'Gap Fixed', _gap_fix: true }, geometry: buffered.geometry });
                                report.fixed_gap++;
                                report.issues.push({ type: 'fixed_gap', name: 'Gap patch', message: 'Pengo limejazwa', feature: out[out.length - 1] });
                            }
                        }
                    }
                }
            } catch (e) { /* skip */ }
        }

        return {
            featureCollection: { type: 'FeatureCollection', features: out },
            report: report
        };
    }

    function updateUpperDashboard(data) {
        var el;
        el = document.getElementById('ud-features');
        if (el) el.textContent = data.featureCount != null ? data.featureCount : '—';
        el = document.getElementById('ud-errors');
        if (el) el.textContent = data.errorCount != null ? data.errorCount : '0';
        el = document.getElementById('ud-warnings');
        if (el) el.textContent = data.warningCount != null ? data.warningCount : '0';
        el = document.getElementById('ud-fixed');
        if (el) el.textContent = data.fixedCount != null ? data.fixedCount : '0';
        el = document.getElementById('ud-quality');
        if (el) {
            var q = data.quality != null ? data.quality : 100;
            el.textContent = q + '%';
            el.style.color = q >= 80 ? '#28a745' : q >= 50 ? '#ff9800' : '#dc3545';
        }
        el = document.getElementById('ud-status');
        if (el) el.textContent = data.status || 'Tayari';

        var tbody = document.getElementById('gis-issues-tbody');
        if (!tbody) return;
        var rows = data.rows || [];
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#999;">Hakuna matokeo bado</td></tr>';
            return;
        }
        tbody.innerHTML = rows.slice(0, 50).map(function (r) {
            var style = ISSUE_STYLES[r.type] || {};
            return '<tr class="issue-row issue-' + r.type + '">' +
                '<td><span class="issue-badge" style="background:' + (style.color || '#666') + '">' + (style.label || r.type) + '</span></td>' +
                '<td>' + (r.name || '—') + '</td>' +
                '<td>' + (r.message || '') + '</td>' +
                '<td><button class="btn btn-sm btn-primary" onclick="GisTools.zoomToIssue(' + r._id + ')"><i class="fas fa-search-location"></i></button></td>' +
                '</tr>';
        }).join('');
        if (rows.length > 50) {
            tbody.innerHTML += '<tr><td colspan="4" style="text-align:center;font-size:10px;color:#888;">+ ' + (rows.length - 50) + ' zingine</td></tr>';
        }
    }

    var _issueRegistry = [];
    var _highlightGroup = null;

    function highlightOnMap(map, issues, activeLayers) {
        if (_highlightGroup && map) map.removeLayer(_highlightGroup);
        _issueRegistry = [];
        _highlightGroup = L.layerGroup().addTo(map);

        issues.forEach(function (issue, id) {
            if (!issue.feature || !issue.feature.geometry) return;
            var style = ISSUE_STYLES[issue.type] || ISSUE_STYLES.invalid;
            try {
                var layer = L.geoJSON(issue.feature, {
                    style: {
                        color: style.color, weight: 3, fillColor: style.fillColor, fillOpacity: 0.45
                    }
                }).bindPopup('<b>' + (style.label || issue.type) + '</b><br>' + (issue.message || issue.name || ''));
                layer.addTo(_highlightGroup);
                issue._id = id;
                _issueRegistry[id] = layer;
            } catch (e) { /* skip */ }
        });

        if (activeLayers) {
            activeLayers.push({ name: 'GIS Issues', layer: _highlightGroup });
        }
        return _highlightGroup;
    }

    function zoomToIssue(id) {
        var layer = _issueRegistry[id];
        if (layer && global.map) {
            try {
                global.map.fitBounds(layer.getBounds(), { padding: [40, 40] });
            } catch (e) { /* skip */ }
        }
    }

    function clearHighlights(map) {
        if (_highlightGroup && map) map.removeLayer(_highlightGroup);
        _highlightGroup = null;
        _issueRegistry = [];
    }

    global.GisTools = {
        QGIS_RULES: QGIS_RULES,
        ISSUE_STYLES: ISSUE_STYLES,
        runQgisTopology: runQgisTopology,
        cleanGeoJSON: cleanGeoJSON,
        updateUpperDashboard: updateUpperDashboard,
        highlightOnMap: highlightOnMap,
        clearHighlights: clearHighlights,
        zoomToIssue: zoomToIssue,
        featName: featName,
        /** Server GDAL/GEOS — sahihi kama QGIS */
        runQgisTopologyServer: function (geojson, rules, minAreaSqM) {
            return fetch('/api/tools/topology-check/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    geojson: geojson,
                    rules: rules,
                    min_area_sqm: minAreaSqM || 100
                })
            }).then(function (r) { return r.json(); });
        },
        /** Server Mapshaper -clean style — GEOS */
        cleanGeoJSONServer: function (geojson, options) {
            return fetch('/api/tools/clean/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ geojson: geojson, options: options || {} })
            }).then(function (r) { return r.json(); });
        },
        runEditCommandServer: function (geojson, command, params) {
            return fetch('/api/tools/edit-command/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    geojson: geojson,
                    command: command,
                    params: params || {}
                })
            }).then(function (r) { return r.json(); });
        },
        SERVER_EDIT_COMMANDS: {
            buffer: true, dissolve: true, dissolve2: true, union: true, mosaic: true,
            simplify: true, clean: true, explode: true, 'filter-slivers': true
        }
    };
})(window);
