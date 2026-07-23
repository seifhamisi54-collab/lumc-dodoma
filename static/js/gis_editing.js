/**
 * GIS Editing Commands — Mapshaper-style geometry & attribute operations (Turf.js)
 */
(function (global) {
    'use strict';

    if (typeof turf === 'undefined') {
        console.warn('gis_editing.js requires Turf.js');
    }

    var CATEGORIES = {
        transform: 'Transform & Buffer',
        topology: 'Topology & Overlay',
        filter: 'Filter & Select',
        conversion: 'Geometry Conversion',
        grid: 'Grid & Frames',
        fields: 'Fields & Attributes',
        style: 'Style & Symbols',
        layers: 'Layer Operations',
        info: 'Information'
    };

    var COMMANDS = [
        { id: 'affine', category: 'transform', name: '-affine', desc: 'Hamisha, panua, zungusha kuratibu', params: [
            { id: 'dx', label: 'Shift X (°)', type: 'number', default: 0 },
            { id: 'dy', label: 'Shift Y (°)', type: 'number', default: 0 },
            { id: 'scale', label: 'Scale', type: 'number', default: 1 },
            { id: 'angle', label: 'Rotate (°)', type: 'number', default: 0 }
        ]},
        { id: 'buffer', category: 'transform', name: '-buffer', desc: 'Ongeza buffer kwa point/line/polygon', params: [
            { id: 'distance', label: 'Umbali (m)', type: 'number', default: 100 },
            { id: 'units', label: 'Units', type: 'select', options: ['meters', 'kilometers', 'feet'], default: 'meters' }
        ]},
        { id: 'simplify', category: 'transform', name: '-simplify', desc: 'Rahisisha jiometri', params: [
            { id: 'tolerance', label: 'Tolerance', type: 'number', default: 0.001 },
            { id: 'highQuality', label: 'High quality', type: 'checkbox', default: true }
        ]},
        { id: 'snap', category: 'transform', name: '-snap', desc: 'Unganisha vertices zilizo karibu', params: [
            { id: 'tolerance', label: 'Tolerance (°)', type: 'number', default: 0.0001 }
        ]},
        { id: 'clean', category: 'topology', name: '-clean', desc: 'Rekebisha overlaps, gaps, invalid geometry', params: [
            { id: 'minArea', label: 'Min area (m²)', type: 'number', default: 100 }
        ]},
        { id: 'dissolve', category: 'topology', name: '-dissolve', desc: 'Unganisha features kwa uwanja wa data', params: [
            { id: 'field', label: 'Uwanja wa kuunganisha', type: 'text', default: 'name', placeholder: 'name' }
        ]},
        { id: 'union', category: 'topology', name: '-union', desc: 'Unda mosaic bapa kutoka polygons', params: [] },
        { id: 'mosaic', category: 'topology', name: '-mosaic', desc: 'Badilisha overlaps kuwa mosaic bapa', params: [] },
        { id: 'clip', category: 'topology', name: '-clip', desc: 'Kata layer kwa polygon ya clip', params: [
            { id: 'clipSource', label: 'Clip kutoka', type: 'select', options: ['map-bounds', 'convex-hull'], default: 'map-bounds' }
        ]},
        { id: 'erase', category: 'topology', name: '-erase', desc: 'Futa sehemu ya layer kwa polygon', params: [
            { id: 'clipSource', label: 'Erase mask', type: 'select', options: ['map-bounds', 'convex-hull'], default: 'convex-hull' }
        ]},
        { id: 'explode', category: 'topology', name: '-explode', desc: 'Gawanya multi-part kuwa single-part', params: [] },
        { id: 'innerlines', category: 'topology', name: '-innerlines', desc: 'Polylines kwenye mipaka ya pamoja', params: [] },
        { id: 'filter', category: 'filter', name: '-filter', desc: 'Chagua features kwa expression (JS)', params: [
            { id: 'expression', label: 'Expression', type: 'text', default: 'f.properties.name', placeholder: 'f.properties.area > 1000' }
        ]},
        { id: 'filter-fields', category: 'filter', name: '-filter-fields', desc: 'Weka fields chache tu', params: [
            { id: 'fields', label: 'Fields (comma)', type: 'text', default: 'name', placeholder: 'name,id,area' }
        ]},
        { id: 'filter-slivers', category: 'filter', name: '-filter-slivers', desc: 'Ondoa polygon ndogo (slivers)', params: [
            { id: 'minArea', label: 'Min area (m²)', type: 'number', default: 100 }
        ]},
        { id: 'filter-islands', category: 'filter', name: '-filter-islands', desc: 'Ondoa pete ndogo zilizotengana', params: [
            { id: 'minArea', label: 'Min area (m²)', type: 'number', default: 50 }
        ]},
        { id: 'uniq', category: 'filter', name: '-uniq', desc: 'Ondoa duplicates kwa geometry', params: [] },
        { id: 'sort', category: 'filter', name: '-sort', desc: 'Panga features kwa expression', params: [
            { id: 'expression', label: 'Sort key', type: 'text', default: 'f.properties.name || ""' }
        ]},
        { id: 'drop', category: 'filter', name: '-drop', desc: 'Futa features kwa expression', params: [
            { id: 'expression', label: 'Drop if true', type: 'text', default: '!f.geometry', placeholder: '!f.properties.name' }
        ]},
        { id: 'lines', category: 'conversion', name: '-lines', desc: 'Badilisha polygon/point kuwa lines', params: [] },
        { id: 'points', category: 'conversion', name: '-points', desc: 'Unda point layer (centroid)', params: [] },
        { id: 'polygons', category: 'conversion', name: '-polygons', desc: 'Funga lines kuwa polygons', params: [] },
        { id: 'divide', category: 'conversion', name: '-divide', desc: 'Kata lines kwa polygons (bbox)', params: [] },
        { id: 'grid', category: 'grid', name: '-grid', desc: 'Grid ya mraba/hex/triangle', params: [
            { id: 'cellSize', label: 'Cell size (km)', type: 'number', default: 5 },
            { id: 'type', label: 'Aina', type: 'select', options: ['square', 'hex', 'triangle'], default: 'square' }
        ]},
        { id: 'point-grid', category: 'grid', name: '-point-grid', desc: 'Grid ya pointi mraba', params: [
            { id: 'cellSize', label: 'Cell size (km)', type: 'number', default: 2 }
        ]},
        { id: 'graticule', category: 'grid', name: '-graticule', desc: 'Graticule (lat/lon grid)', params: [
            { id: 'step', label: 'Hatua (°)', type: 'number', default: 1 }
        ]},
        { id: 'rectangle', category: 'grid', name: '-rectangle', desc: 'Unda rectangle kutoka bbox ya data', params: [] },
        { id: 'rectangles', category: 'grid', name: '-rectangles', desc: 'Rectangle kwa kila feature', params: [] },
        { id: 'each', category: 'fields', name: '-each', desc: 'Badilisha properties kwa JS', params: [
            { id: 'expression', label: 'JS body', type: 'text', default: 'f.properties.area_m2 = turf.area(f);', placeholder: 'f.properties.id = i' }
        ]},
        { id: 'rename-fields', category: 'fields', name: '-rename-fields', desc: 'Badilisha majina ya fields', params: [
            { id: 'map', label: 'old:new pairs', type: 'text', default: 'name:NAME', placeholder: 'old1:new1,old2:new2' }
        ]},
        { id: 'classify', category: 'style', name: '-classify', desc: 'Weka rangi kwa thamani ya field', params: [
            { id: 'field', label: 'Field', type: 'text', default: 'name' },
            { id: 'method', label: 'Method', type: 'select', options: ['categorical', 'quantile'], default: 'categorical' }
        ]},
        { id: 'style', category: 'style', name: '-style', desc: 'Weka rangi/weight kwa properties', params: [
            { id: 'stroke', label: 'Stroke color', type: 'text', default: '#1565c0' },
            { id: 'fill', label: 'Fill color', type: 'text', default: '#42a5f5' },
            { id: 'width', label: 'Weight', type: 'number', default: 2 }
        ]},
        { id: 'symbols', category: 'style', name: '-symbols', desc: 'Point symbols (circle/square)', params: [
            { id: 'symbol', label: 'Symbol', type: 'select', options: ['circle', 'square', 'triangle'], default: 'circle' },
            { id: 'radius', label: 'Radius', type: 'number', default: 6 }
        ]},
        { id: 'dots', category: 'style', name: '-dots', desc: 'Jaza polygon kwa dots', params: [
            { id: 'spacing', label: 'Spacing (km)', type: 'number', default: 1 }
        ]},
        { id: 'merge-layers', category: 'layers', name: '-merge-layers', desc: 'Unganisha layers zilizo hai', params: [] },
        { id: 'split', category: 'layers', name: '-split', desc: 'Gawanya kwa field (group)', params: [
            { id: 'field', label: 'Field', type: 'text', default: 'name' }
        ]},
        { id: 'calc', category: 'info', name: '-calc', desc: 'Hesabu takwimu za layer', params: [], infoOnly: false },
        { id: 'info', category: 'info', name: '-info', desc: 'Taarifa za layer', params: [], infoOnly: false },
        { id: 'inspect', category: 'info', name: '-inspect', desc: 'Angalia feature #0', params: [
            { id: 'index', label: 'Feature index', type: 'number', default: 0 }
        ]},
        { id: 'dissolve2', category: 'topology', name: '-dissolve2', desc: 'Alias ya -dissolve (deprecated)', params: [
            { id: 'field', label: 'Field', type: 'text', default: 'name' }
        ], deprecated: true },
        { id: 'colorizer', category: 'style', name: '-colorizer', desc: 'Color ramp kwa thamani (SVG)', infoOnly: true },
        { id: 'dashlines', category: 'conversion', name: '-dashlines', desc: 'Gawanya lines na gaps (SVG)', infoOnly: true },
        { id: 'inlay', category: 'topology', name: '-inlay', desc: 'Weka polygon ndani ya nyingine', infoOnly: true },
        { id: 'join', category: 'fields', name: '-join', desc: 'Join na file nyingine (pakua GeoJSON)', infoOnly: true },
        { id: 'proj', category: 'transform', name: '-proj', desc: 'Projection (Proj.4) — tumia WGS84 kwenye browser', infoOnly: true },
        { id: 'split-on-grid', category: 'layers', name: '-split-on-grid', desc: 'Gawanya kwa grid cells', infoOnly: true },
        { id: 'rename-layers', category: 'layers', name: '-rename-layers', desc: 'Badilisha jina la layer', infoOnly: true },
        { id: 'target', category: 'layers', name: '-target', desc: 'Weka active layer', infoOnly: true },
        { id: 'cluster', category: 'topology', name: '-cluster', desc: 'Experimental: cluster polygons', experimental: true, params: [
            { id: 'count', label: 'Clusters', type: 'number', default: 5 }
        ]},
        { id: 'data-fill', category: 'fields', name: '-data-fill', desc: 'Experimental: jaza thamani zilizokosekana', experimental: true, params: [
            { id: 'field', label: 'Field', type: 'text', default: 'name' },
            { id: 'value', label: 'Default', type: 'text', default: 'unknown' }
        ]},
        { id: 'shape', category: 'grid', name: '-shape', desc: 'Unda polyline/polygon kutoka coords', infoOnly: true },
        { id: 'subdivide', category: 'topology', name: '-subdivide', desc: 'Experimental: gawanya recursively', experimental: true, infoOnly: true },
        { id: 'fuzzy-join', category: 'fields', name: '-fuzzy-join', desc: 'Experimental: fuzzy join', experimental: true, infoOnly: true },
        { id: 'frame', category: 'grid', name: '-frame', desc: 'Experimental: map frame', experimental: true, infoOnly: true },
        { id: 'scalebar', category: 'style', name: '-scalebar', desc: 'Experimental: scale bar SVG', experimental: true, infoOnly: true },
        { id: 'include', category: 'info', name: '-include', desc: 'Import JS kwa expressions', infoOnly: true },
        { id: 'require', category: 'info', name: '-require', desc: 'Require Node module', infoOnly: true },
        { id: 'run', category: 'info', name: '-run', desc: 'Endesha command file', infoOnly: true },
        { id: 'if', category: 'info', name: '-if', desc: 'Control flow: if', infoOnly: true },
        { id: 'elif', category: 'info', name: '-elif', desc: 'Control flow: elif', infoOnly: true },
        { id: 'else', category: 'info', name: '-else', desc: 'Control flow: else', infoOnly: true },
        { id: 'endif', category: 'info', name: '-endif', desc: 'Control flow: endif', infoOnly: true },
        { id: 'stop', category: 'info', name: '-stop', desc: 'Acha processing', infoOnly: true },
        { id: 'comment', category: 'info', name: '-comment', desc: 'Maelezo tu', infoOnly: true },
        { id: 'help', category: 'info', name: '-help', desc: 'Msaada wa amri', infoOnly: true },
        { id: 'print', category: 'info', name: '-print', desc: 'Chapisha ujumbe', infoOnly: true },
        { id: 'projections', category: 'info', name: '-projections', desc: 'Orodha ya projections', infoOnly: true },
        { id: 'colors', category: 'info', name: '-colors', desc: 'Orodha ya color schemes', infoOnly: true },
        { id: 'encodings', category: 'info', name: '-encodings', desc: 'Text encodings', infoOnly: true },
        { id: 'quiet', category: 'info', name: '-quiet', desc: 'Zima ujumbe', infoOnly: true },
        { id: 'defaults', category: 'info', name: '-defaults', desc: 'Weka variables default', infoOnly: true },
        { id: 'vars', category: 'info', name: '-vars', desc: 'Fafanua {{VAR}}', infoOnly: true }
    ];

    var PALETTE = ['#e53935', '#8e24aa', '#3949ab', '#1e88e5', '#00897b', '#7cb342', '#f9a825', '#fb8c00', '#6d4c41', '#546e7a'];

    function cloneFC(fc) {
        return JSON.parse(JSON.stringify(fc || { type: 'FeatureCollection', features: [] }));
    }

    function features(fc) {
        return (fc && fc.features) ? fc.features : [];
    }

    function toFC(feats) {
        return { type: 'FeatureCollection', features: feats || [] };
    }

    function bboxOf(fc) {
        if (!fc || !fc.features.length) return null;
        try { return turf.bbox(fc); } catch (e) { return null; }
    }

    function evalExpr(expr, f, i) {
        var fn = new Function('f', 'i', 'turf', 'return (' + expr + ');');
        return fn(f, i, turf);
    }

    function runExpr(expr, f, i) {
        var fn = new Function('f', 'i', 'turf', expr);
        fn(f, i, turf);
    }

    function explodeFeatures(feats) {
        var out = [];
        feats.forEach(function (f) {
            if (!f || !f.geometry) return;
            var g = f.geometry;
            if (g.type === 'MultiPolygon') {
                g.coordinates.forEach(function (poly) {
                    out.push({ type: 'Feature', properties: Object.assign({}, f.properties), geometry: { type: 'Polygon', coordinates: poly } });
                });
            } else if (g.type === 'MultiLineString') {
                g.coordinates.forEach(function (line) {
                    out.push({ type: 'Feature', properties: Object.assign({}, f.properties), geometry: { type: 'LineString', coordinates: line } });
                });
            } else if (g.type === 'MultiPoint') {
                g.coordinates.forEach(function (pt) {
                    out.push({ type: 'Feature', properties: Object.assign({}, f.properties), geometry: { type: 'Point', coordinates: pt } });
                });
            } else {
                out.push(JSON.parse(JSON.stringify(f)));
            }
        });
        return out;
    }

    function snapVertices(feats, tolerance) {
        var coords = [];
        feats.forEach(function (f) {
            if (!f.geometry) return;
            turf.coordEach(f, function (c) { coords.push(c); });
        });
        return feats.map(function (f) {
            var copy = JSON.parse(JSON.stringify(f));
            turf.coordEach(copy, function (c) {
                coords.forEach(function (ref) {
                    if (Math.abs(c[0] - ref[0]) < tolerance && Math.abs(c[1] - ref[1]) < tolerance) {
                        c[0] = ref[0];
                        c[1] = ref[1];
                    }
                });
            });
            return copy;
        });
    }

    function dissolveByField(feats, field) {
        var groups = {};
        feats.forEach(function (f) {
            var key = (f.properties && f.properties[field] != null) ? String(f.properties[field]) : '__null__';
            if (!groups[key]) groups[key] = [];
            groups[key].push(f);
        });
        var out = [];
        Object.keys(groups).forEach(function (key) {
            var polys = groups[key].filter(function (f) {
                return f.geometry && f.geometry.type.indexOf('Polygon') !== -1;
            });
            if (!polys.length) {
                out = out.concat(groups[key]);
                return;
            }
            try {
                var union = turf.feature(polys[0].geometry, Object.assign({}, polys[0].properties || {}, { [field]: key === '__null__' ? null : key }));
                for (var i = 1; i < polys.length; i++) {
                    try { union = turf.union(union, turf.feature(polys[i].geometry)); } catch (e2) { /* skip */ }
                }
                union.properties = Object.assign({}, polys[0].properties || {}, { [field]: key === '__null__' ? null : key });
                out.push(union);
            } catch (e) {
                out = out.concat(groups[key]);
            }
        });
        return out;
    }

    function unionAll(feats) {
        var polys = feats.filter(function (f) { return f.geometry && f.geometry.type.indexOf('Polygon') !== -1; });
        if (!polys.length) return feats;
        try {
            var u = turf.feature(polys[0].geometry, { name: 'union' });
            for (var i = 1; i < polys.length; i++) {
                try { u = turf.union(u, turf.feature(polys[i].geometry)); } catch (e) { /* skip */ }
            }
            return [u];
        } catch (e) {
            return feats;
        }
    }

    function clipMask(fc, source, mapBounds) {
        if (source === 'map-bounds' && mapBounds) {
            var sw = mapBounds.getSouthWest();
            var ne = mapBounds.getNorthEast();
            return turf.bboxPolygon([sw.lng, sw.lat, ne.lng, ne.lat]);
        }
        try {
            var collection = turf.featureCollection(fc.features.filter(function (f) { return f.geometry; }).map(function (f) { return turf.feature(f.geometry); }));
            return turf.convex(collection) || turf.bboxPolygon(bboxOf(fc));
        } catch (e) {
            return turf.bboxPolygon(bboxOf(fc));
        }
    }

    function cmdAffine(fc, p) {
        var dx = parseFloat(p.dx) || 0;
        var dy = parseFloat(p.dy) || 0;
        var scale = parseFloat(p.scale) || 1;
        var angle = parseFloat(p.angle) || 0;
        var out = features(fc).map(function (f) {
            var tf = turf.feature(f.geometry, f.properties);
            if (angle) tf = turf.transformRotate(tf, angle);
            if (scale !== 1) tf = turf.transformScale(tf, scale);
            if (dx || dy) {
                turf.coordEach(tf, function (c) {
                    c[0] += dx;
                    c[1] += dy;
                });
            }
            return { type: 'Feature', properties: f.properties || {}, geometry: tf.geometry };
        });
        return { fc: toFC(out), message: 'Affine imetumika kwa features ' + out.length };
    }

    function cmdBuffer(fc, p) {
        var dist = parseFloat(p.distance) || 100;
        var units = p.units || 'meters';
        var out = features(fc).map(function (f) {
            try {
                var buf = turf.buffer(turf.feature(f.geometry), dist, { units: units });
                return { type: 'Feature', properties: Object.assign({}, f.properties, { buffer_m: dist }), geometry: buf.geometry };
            } catch (e) { return f; }
        });
        return { fc: toFC(out), message: 'Buffer ' + dist + ' ' + units };
    }

    function cmdSimplify(fc, p) {
        var tol = parseFloat(p.tolerance) || 0.001;
        var hq = p.highQuality !== false && p.highQuality !== 'false';
        var out = features(fc).map(function (f) {
            try {
                var s = turf.simplify(turf.feature(f.geometry), { tolerance: tol, highQuality: hq });
                return { type: 'Feature', properties: f.properties || {}, geometry: s.geometry };
            } catch (e) { return f; }
        });
        return { fc: toFC(out), message: 'Simplify tolerance=' + tol };
    }

    function cmdSnap(fc, p) {
        var tol = parseFloat(p.tolerance) || 0.0001;
        return { fc: toFC(snapVertices(features(fc), tol)), message: 'Snap tolerance=' + tol };
    }

    function cmdClean(fc, p) {
        if (!global.GisTools) return { fc: fc, message: 'GisTools haipatikani' };
        var minArea = parseFloat(p.minArea) || 100;
        var result = GisTools.cleanGeoJSON(features(fc), {
            fix_gaps: true, fix_overlaps: true, fix_invalid: true,
            remove_duplicates: true, remove_slivers: true, fix_coords: true,
            minAreaSqM: minArea
        });
        return { fc: result.featureCollection, message: 'Clean: ' + result.report.fixed_invalid + ' invalid, ' + result.report.fixed_overlap + ' overlaps' };
    }

    function cmdDissolve(fc, p) {
        var field = p.field || 'name';
        var out = dissolveByField(features(fc), field);
        return { fc: toFC(out), message: 'Dissolve kwa field "' + field + '" → ' + out.length + ' features' };
    }

    function cmdUnion(fc) {
        return { fc: toFC(unionAll(features(fc))), message: 'Union imekamilika' };
    }

    function cmdMosaic(fc) {
        return cmdUnion(fc);
    }

    function cmdClip(fc, p, ctx) {
        var mask = clipMask(fc, p.clipSource || 'map-bounds', ctx.mapBounds);
        var out = [];
        features(fc).forEach(function (f) {
            try {
                var inter = turf.intersect(turf.feature(f.geometry), mask);
                if (inter) out.push({ type: 'Feature', properties: f.properties || {}, geometry: inter.geometry });
            } catch (e) { /* skip */ }
        });
        return { fc: toFC(out), message: 'Clip: ' + out.length + ' features' };
    }

    function cmdErase(fc, p, ctx) {
        var mask = clipMask(fc, p.clipSource || 'convex-hull', ctx.mapBounds);
        var out = [];
        features(fc).forEach(function (f) {
            try {
                var diff = turf.difference(turf.feature(f.geometry), mask);
                if (diff) out.push({ type: 'Feature', properties: f.properties || {}, geometry: diff.geometry });
            } catch (e) { /* skip */ }
        });
        return { fc: toFC(out), message: 'Erase: ' + out.length + ' features' };
    }

    function cmdExplode(fc) {
        var out = explodeFeatures(features(fc));
        return { fc: toFC(out), message: 'Explode → ' + out.length + ' features' };
    }

    function cmdInnerlines(fc) {
        var lines = [];
        features(fc).forEach(function (f) {
            if (!f.geometry) return;
            try {
                if (f.geometry.type.indexOf('Polygon') !== -1) {
                    var ln = turf.polygonToLine(turf.feature(f.geometry));
                    if (ln.type === 'Feature') lines.push(ln);
                    else if (ln.features) lines = lines.concat(ln.features);
                }
            } catch (e) { /* skip */ }
        });
        return { fc: toFC(lines), message: 'Innerlines/boundaries: ' + lines.length };
    }

    function cmdFilter(fc, p) {
        var expr = p.expression || 'true';
        var out = features(fc).filter(function (f, i) {
            try { return !!evalExpr(expr, f, i); } catch (e) { return false; }
        });
        return { fc: toFC(out), message: 'Filter: ' + out.length + ' zimesalia' };
    }

    function cmdFilterFields(fc, p) {
        var keep = (p.fields || 'name').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        var out = features(fc).map(function (f) {
            var props = {};
            keep.forEach(function (k) { if (f.properties && f.properties[k] !== undefined) props[k] = f.properties[k]; });
            return { type: 'Feature', properties: props, geometry: f.geometry };
        });
        return { fc: toFC(out), message: 'Fields: ' + keep.join(', ') };
    }

    function cmdFilterSlivers(fc, p) {
        var min = parseFloat(p.minArea) || 100;
        var out = features(fc).filter(function (f) {
            if (!f.geometry || f.geometry.type.indexOf('Polygon') === -1) return true;
            try { return turf.area(turf.feature(f.geometry)) >= min; } catch (e) { return false; }
        });
        return { fc: toFC(out), message: 'Slivers < ' + min + ' m² zimeondolewa' };
    }

    function cmdFilterIslands(fc, p) {
        return cmdFilterSlivers(fc, p);
    }

    function cmdUniq(fc) {
        var seen = {};
        var out = features(fc).filter(function (f) {
            var key = JSON.stringify(f.geometry);
            if (seen[key]) return false;
            seen[key] = true;
            return true;
        });
        return { fc: toFC(out), message: 'Uniq: ' + out.length + ' features' };
    }

    function cmdSort(fc, p) {
        var expr = p.expression || '""';
        var out = features(fc).slice().sort(function (a, b) {
            var va = '', vb = '';
            try { va = evalExpr(expr, a, 0); vb = evalExpr(expr, b, 0); } catch (e) { /* skip */ }
            return va > vb ? 1 : va < vb ? -1 : 0;
        });
        return { fc: toFC(out), message: 'Sorted ' + out.length + ' features' };
    }

    function cmdDrop(fc, p) {
        var expr = p.expression || 'false';
        var out = features(fc).filter(function (f, i) {
            try { return !evalExpr(expr, f, i); } catch (e) { return true; }
        });
        return { fc: toFC(out), message: 'Drop: ' + (features(fc).length - out.length) + ' zimeondolewa' };
    }

    function cmdLines(fc) {
        var out = [];
        features(fc).forEach(function (f) {
            if (!f.geometry) return;
            try {
                if (f.geometry.type.indexOf('Polygon') !== -1) {
                    var ln = turf.polygonToLine(turf.feature(f.geometry));
                    if (ln.type === 'Feature') out.push({ type: 'Feature', properties: f.properties, geometry: ln.geometry });
                    else if (ln.features) ln.features.forEach(function (lf) { out.push({ type: 'Feature', properties: f.properties, geometry: lf.geometry }); });
                } else if (f.geometry.type === 'Point') {
                    out.push(f);
                } else {
                    out.push(f);
                }
            } catch (e) { out.push(f); }
        });
        return { fc: toFC(out), message: 'Lines: ' + out.length };
    }

    function cmdPoints(fc) {
        var out = features(fc).map(function (f) {
            if (!f.geometry) return f;
            try {
                var c = turf.centroid(turf.feature(f.geometry));
                return { type: 'Feature', properties: f.properties || {}, geometry: c.geometry };
            } catch (e) { return f; }
        });
        return { fc: toFC(out), message: 'Points (centroid): ' + out.length };
    }

    function cmdPolygons(fc) {
        var out = [];
        features(fc).forEach(function (f) {
            if (!f.geometry) return;
            try {
                if (f.geometry.type.indexOf('Line') !== -1) {
                    var poly = turf.lineToPolygon(turf.feature(f.geometry));
                    out.push({ type: 'Feature', properties: f.properties, geometry: poly.geometry });
                } else {
                    out.push(f);
                }
            } catch (e) { /* skip */ }
        });
        return { fc: toFC(out), message: 'Polygons: ' + out.length };
    }

    function cmdDivide(fc) {
        var bb = bboxOf(fc);
        if (!bb) return { fc: fc, message: 'Hakuna bbox' };
        var mask = turf.bboxPolygon(bb);
        return cmdClip(fc, { clipSource: 'map-bounds' }, { mapBounds: { getSouthWest: function () { return { lng: bb[0], lat: bb[1] }; }, getNorthEast: function () { return { lng: bb[2], lat: bb[3] }; } } });
    }

    function cmdGrid(fc, p, ctx) {
        var bb = bboxOf(fc) || (ctx.mapBounds ? [-180, -85, 180, 85] : [33, -12, 40, -1]);
        var cell = parseFloat(p.cellSize) || 5;
        var type = p.type || 'square';
        var grid;
        if (type === 'hex' && turf.hexGrid) grid = turf.hexGrid(bb, cell, { units: 'kilometers' });
        else if (type === 'triangle' && turf.triangleGrid) grid = turf.triangleGrid(bb, cell, { units: 'kilometers' });
        else grid = turf.squareGrid(bb, cell, { units: 'kilometers' });
        return { fc: grid, message: type + ' grid cell=' + cell + 'km' };
    }

    function cmdPointGrid(fc, p, ctx) {
        var bb = bboxOf(fc) || [33, -12, 40, -1];
        var cell = parseFloat(p.cellSize) || 2;
        var grid = turf.pointGrid(bb, cell, { units: 'kilometers' });
        return { fc: grid, message: 'Point grid: ' + grid.features.length };
    }

    function cmdGraticule(fc, p, ctx) {
        var bb = bboxOf(fc) || [33, -12, 40, -1];
        var step = parseFloat(p.step) || 1;
        var lines = [];
        for (var lon = Math.floor(bb[0]); lon <= Math.ceil(bb[2]); lon += step) {
            lines.push(turf.lineString([[lon, bb[1]], [lon, bb[3]]], { type: 'meridian', lon: lon }));
        }
        for (var lat = Math.floor(bb[1]); lat <= Math.ceil(bb[3]); lat += step) {
            lines.push(turf.lineString([[bb[0], lat], [bb[2], lat]], { type: 'parallel', lat: lat }));
        }
        return { fc: toFC(lines), message: 'Graticule step=' + step + '°' };
    }

    function cmdRectangle(fc) {
        var bb = bboxOf(fc);
        if (!bb) return { fc: toFC([]), message: 'Hakuna data' };
        return { fc: toFC([turf.bboxPolygon(bb)]), message: 'Rectangle kutoka bbox' };
    }

    function cmdRectangles(fc) {
        var out = features(fc).map(function (f) {
            try {
                var bb = turf.bbox(turf.feature(f.geometry));
                return turf.bboxPolygon(bb, f.properties || {});
            } catch (e) { return f; }
        });
        return { fc: toFC(out), message: 'Rectangles: ' + out.length };
    }

    function cmdEach(fc, p) {
        var expr = p.expression || '';
        var out = features(fc).map(function (f, i) {
            var copy = JSON.parse(JSON.stringify(f));
            try { runExpr(expr, copy, i); } catch (e) { /* skip */ }
            return copy;
        });
        return { fc: toFC(out), message: 'Each: fields zimesasishwa' };
    }

    function cmdRenameFields(fc, p) {
        var pairs = (p.map || '').split(',').map(function (s) { return s.trim().split(':'); });
        var out = features(fc).map(function (f) {
            var props = Object.assign({}, f.properties || {});
            pairs.forEach(function (pair) {
                if (pair.length === 2 && props[pair[0]] !== undefined) {
                    props[pair[1]] = props[pair[0]];
                    delete props[pair[0]];
                }
            });
            return { type: 'Feature', properties: props, geometry: f.geometry };
        });
        return { fc: toFC(out), message: 'Rename fields imekamilika' };
    }

    function cmdClassify(fc, p) {
        var field = p.field || 'name';
        var vals = {};
        var idx = 0;
        var out = features(fc).map(function (f) {
            var props = Object.assign({}, f.properties || {});
            var v = props[field] != null ? String(props[field]) : '__';
            if (!vals[v]) vals[v] = PALETTE[idx++ % PALETTE.length];
            props._color = vals[v];
            props._class = v;
            return { type: 'Feature', properties: props, geometry: f.geometry };
        });
        return { fc: toFC(out), message: 'Classify: ' + Object.keys(vals).length + ' classes' };
    }

    function cmdStyle(fc, p) {
        var out = features(fc).map(function (f) {
            return {
                type: 'Feature',
                properties: Object.assign({}, f.properties, {
                    stroke: p.stroke || '#1565c0',
                    fill: p.fill || '#42a5f5',
                    weight: parseFloat(p.width) || 2
                }),
                geometry: f.geometry
            };
        });
        return { fc: toFC(out), message: 'Style imewekwa' };
    }

    function cmdSymbols(fc, p) {
        var sym = p.symbol || 'circle';
        var r = parseFloat(p.radius) || 6;
        var pts = cmdPoints(fc).fc;
        pts.features.forEach(function (f) {
            f.properties = Object.assign({}, f.properties, { symbol: sym, radius: r });
        });
        return { fc: pts, message: 'Symbols: ' + sym };
    }

    function cmdDots(fc, p) {
        var spacing = parseFloat(p.spacing) || 1;
        var dots = [];
        features(fc).forEach(function (f) {
            if (!f.geometry || f.geometry.type.indexOf('Polygon') === -1) return;
            try {
                var bb = turf.bbox(turf.feature(f.geometry));
                var grid = turf.pointGrid(bb, spacing, { units: 'kilometers' });
                grid.features.forEach(function (pt) {
                    if (turf.booleanPointInPolygon(pt, turf.feature(f.geometry))) {
                        pt.properties = Object.assign({}, f.properties, { dot: true });
                        dots.push(pt);
                    }
                });
            } catch (e) { /* skip */ }
        });
        return { fc: toFC(dots), message: 'Dots: ' + dots.length };
    }

    function cmdMergeLayers(fc, ctx) {
        var merged = features(fc).slice();
        (ctx.extraLayers || []).forEach(function (extra) {
            if (extra && extra.features) merged = merged.concat(extra.features);
        });
        return { fc: toFC(merged), message: 'Merge: ' + merged.length + ' features' };
    }

    function cmdSplit(fc, p) {
        var field = p.field || 'name';
        var groups = {};
        features(fc).forEach(function (f) {
            var k = (f.properties && f.properties[field] != null) ? String(f.properties[field]) : 'default';
            if (!groups[k]) groups[k] = [];
            groups[k].push(f);
        });
        var keys = Object.keys(groups);
        return { fc: toFC(groups[keys[0]] || []), message: 'Split: ' + keys.length + ' groups (kwanza: ' + (keys[0] || '-') + ')', splitGroups: groups };
    }

    function cmdCluster(fc, p) {
        var n = parseInt(p.count, 10) || 5;
        var polys = features(fc).filter(function (f) { return f.geometry && f.geometry.type.indexOf('Polygon') !== -1; });
        if (polys.length < n) return { fc: fc, message: 'Features chache kwa cluster' };
        var out = polys.map(function (f, i) {
            var copy = JSON.parse(JSON.stringify(f));
            copy.properties = Object.assign({}, copy.properties, { cluster: i % n });
            return copy;
        });
        return { fc: toFC(out), message: 'Cluster (experimental): ' + n + ' groups' };
    }

    function cmdDataFill(fc, p) {
        var field = p.field || 'name';
        var val = p.value || 'unknown';
        var out = features(fc).map(function (f) {
            var props = Object.assign({}, f.properties || {});
            if (props[field] == null || props[field] === '') props[field] = val;
            return { type: 'Feature', properties: props, geometry: f.geometry };
        });
        return { fc: toFC(out), message: 'Data-fill: ' + field + '=' + val };
    }

    function cmdCalc(fc) {
        var feats = features(fc);
        var areas = [], lengths = [];
        feats.forEach(function (f) {
            if (!f.geometry) return;
            try {
                if (f.geometry.type.indexOf('Polygon') !== -1) areas.push(turf.area(turf.feature(f.geometry)));
                if (f.geometry.type.indexOf('Line') !== -1) lengths.push(turf.length(turf.feature(f.geometry), { units: 'kilometers' }));
            } catch (e) { /* skip */ }
        });
        var msg = 'Features: ' + feats.length;
        if (areas.length) msg += ' | Eneo: min=' + Math.min.apply(null, areas).toFixed(0) + ' m², max=' + Math.max.apply(null, areas).toFixed(0) + ' m², jumla=' + areas.reduce(function (a, b) { return a + b; }, 0).toFixed(0) + ' m²';
        if (lengths.length) msg += ' | Urefu: jumla=' + lengths.reduce(function (a, b) { return a + b; }, 0).toFixed(2) + ' km';
        return { fc: fc, message: msg, infoOnly: true };
    }

    function cmdInfo(fc) {
        var types = {};
        features(fc).forEach(function (f) {
            var t = (f.geometry && f.geometry.type) || 'null';
            types[t] = (types[t] || 0) + 1;
        });
        return { fc: fc, message: 'Layer: ' + features(fc).length + ' features | ' + JSON.stringify(types), infoOnly: true };
    }

    function cmdInspect(fc, p) {
        var idx = parseInt(p.index, 10) || 0;
        var f = features(fc)[idx];
        if (!f) return { fc: fc, message: 'Feature #' + idx + ' haipo', infoOnly: true };
        return { fc: fc, message: 'Feature #' + idx + ': ' + JSON.stringify(f, null, 2).slice(0, 800), infoOnly: true };
    }

    var RUNNERS = {
        affine: cmdAffine, buffer: cmdBuffer, simplify: cmdSimplify, snap: cmdSnap,
        clean: cmdClean, dissolve: cmdDissolve, dissolve2: cmdDissolve, union: cmdUnion, mosaic: cmdMosaic,
        clip: cmdClip, erase: cmdErase, explode: cmdExplode, innerlines: cmdInnerlines,
        filter: cmdFilter, 'filter-fields': cmdFilterFields, 'filter-slivers': cmdFilterSlivers,
        'filter-islands': cmdFilterIslands, uniq: cmdUniq, sort: cmdSort, drop: cmdDrop,
        lines: cmdLines, points: cmdPoints, polygons: cmdPolygons, divide: cmdDivide,
        grid: cmdGrid, 'point-grid': cmdPointGrid, graticule: cmdGraticule,
        rectangle: cmdRectangle, rectangles: cmdRectangles,
        each: cmdEach, 'rename-fields': cmdRenameFields,
        classify: cmdClassify, style: cmdStyle, symbols: cmdSymbols, dots: cmdDots,
        'merge-layers': cmdMergeLayers, split: cmdSplit,
        cluster: cmdCluster, 'data-fill': cmdDataFill,
        calc: cmdCalc, info: cmdInfo, inspect: cmdInspect
    };

    function getCommand(id) {
        for (var i = 0; i < COMMANDS.length; i++) {
            if (COMMANDS[i].id === id) return COMMANDS[i];
        }
        return null;
    }

    function runCommand(id, featureCollection, params, context) {
        var cmd = getCommand(id);
        if (!cmd) return { ok: false, message: 'Amri haijulikani: ' + id };
        if (cmd.infoOnly && !RUNNERS[id]) {
            return { ok: true, fc: featureCollection, message: cmd.name + ': ' + cmd.desc + ' (inapatikana kwenye Mapshaper CLI)', infoOnly: true };
        }
        var runner = RUNNERS[id];
        if (!runner) return { ok: false, message: 'Amri ' + id + ' haijatekelezwa bado' };
        if (!featureCollection || !featureCollection.features || !featureCollection.features.length) {
            if (id === 'calc' || id === 'info') {
                var r = runner(featureCollection || toFC([]), params || {}, context || {});
                return { ok: true, fc: r.fc, message: r.message, infoOnly: !!r.infoOnly };
            }
            return { ok: false, message: 'Pakia data kwanza (shapefile/GeoJSON)' };
        }
        try {
            var result = runner(featureCollection, params || {}, context || {});
            return {
                ok: true,
                fc: result.fc,
                message: result.message || (cmd.name + ' imekamilika'),
                infoOnly: !!result.infoOnly,
                splitGroups: result.splitGroups
            };
        } catch (err) {
            return { ok: false, message: 'Hitilafu: ' + (err.message || err) };
        }
    }

    function listByCategory(category) {
        return COMMANDS.filter(function (c) {
            return !category || c.category === category;
        });
    }

    function searchCommands(q) {
        q = (q || '').toLowerCase();
        if (!q) return COMMANDS;
        return COMMANDS.filter(function (c) {
            return c.id.indexOf(q) !== -1 || c.name.indexOf(q) !== -1 || (c.desc && c.desc.toLowerCase().indexOf(q) !== -1);
        });
    }

    global.GisEditing = {
        CATEGORIES: CATEGORIES,
        COMMANDS: COMMANDS,
        getCommand: getCommand,
        runCommand: runCommand,
        listByCategory: listByCategory,
        searchCommands: searchCommands,
        cloneFC: cloneFC
    };
})(window);
