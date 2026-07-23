/**
 * Rangi za Matumizi ya Ardhi — Planning Colour Legend (NLUP / VLUP).
 * RGB kutoka legend rasmi ya Land Use Planning.
 */
var LanduseSymbology = (function() {
    // rgb(r,g,b) → #RRGGBB
    function rgb(r, g, b) {
        function h(n) {
            var s = Number(n).toString(16);
            return s.length === 1 ? '0' + s : s;
        }
        return '#' + h(r) + h(g) + h(b);
    }

    /**
     * Planning colours — fillColor = RGB ya legend; color = outline (kidogo giza).
     */
    var PALETTE = {
        // Settlement — R255 G243 B20
        settlement:        { fillColor: rgb(255, 243, 20),  color: rgb(180, 160, 0),   label: 'Settlement (Makazi)' },
        // Agriculture — R0 G214 B104
        agriculture:       { fillColor: rgb(0, 214, 104),   color: rgb(0, 140, 70),    label: 'Agriculture (Kilimo)' },
        // Agriculture and Settlement — Scrub1, R255 G243 B20
        agric_settlement:  { fillColor: rgb(255, 243, 20),  color: rgb(180, 160, 0),   label: 'Agriculture and Settlement', pattern: 'scrub' },
        // Agric. Irrigation — Scrub1, R23 G168 B32
        agric_irrigation:  { fillColor: rgb(23, 168, 32),   color: rgb(15, 110, 20),   label: 'Agric. Irrigation', pattern: 'scrub' },
        // Mixed Use — 10% cross hatch, R250 G222 B17
        mixed:             { fillColor: rgb(250, 222, 17),  color: rgb(170, 140, 0),   label: 'Mixed Use', pattern: 'hatch' },
        // Grazing — Open Pasture, R227 G158 B0
        grazing:           { fillColor: rgb(227, 158, 0),   color: rgb(160, 100, 0),   label: 'Grazing (Malisho)', pattern: 'pasture' },
        // Forest Reserve / Open Forest / Plantation — R0 G117 B37
        forest_reserve:    { fillColor: rgb(0, 117, 37),    color: rgb(0, 70, 20),     label: 'Forest Reserve (FR)' },
        open_forest:       { fillColor: rgb(0, 117, 37),    color: rgb(0, 70, 20),     label: 'Open Forest (OF)' },
        plantation:        { fillColor: rgb(0, 117, 37),    color: rgb(0, 70, 20),     label: 'Plantation (PL)' },
        // Mangrove — R109 G187 B67
        mangrove:          { fillColor: rgb(109, 187, 67),  color: rgb(60, 120, 35),   label: 'Mangrove Forest' },
        // NP / GCA / GR / WMA — R144 G238 B144
        national_park:     { fillColor: rgb(144, 238, 144), color: rgb(60, 140, 60),   label: 'National Park (NP)' },
        game_controlled:   { fillColor: rgb(144, 238, 144), color: rgb(60, 140, 60),   label: 'Game Controlled Area (GCA)' },
        game_reserve:      { fillColor: rgb(144, 238, 144), color: rgb(60, 140, 60),   label: 'Game Reserve (GR)' },
        wma:               { fillColor: rgb(144, 238, 144), color: rgb(60, 140, 60),   label: 'Wildlife Management Area (WMA)' },
        // Land Bank — R250 G200 B200
        land_bank:         { fillColor: rgb(250, 200, 200), color: rgb(180, 100, 100), label: 'Land Bank (Ardhi ya Akiba)' },
        // Industrial — R215 G160 B250
        industrial:        { fillColor: rgb(215, 160, 250), color: rgb(140, 80, 180),  label: 'Industrial (Viwanda)' },
        // Mining — R255 G125 B0
        mining:            { fillColor: rgb(255, 125, 0),   color: rgb(180, 70, 0),    label: 'Mining (Madini)' },
        // Quarry — gravel pattern
        quarry:            { fillColor: rgb(230, 230, 230), color: rgb(0, 0, 0),       label: 'Quarry', pattern: 'gravel' },
        // Historic Site — R104 G52 B13
        historic:          { fillColor: rgb(240, 230, 220), color: rgb(104, 52, 13),   label: 'Historic Site' },
        // Water Bodies — R151 G219 B242
        water:             { fillColor: rgb(151, 219, 242), color: rgb(70, 140, 180),  label: 'Water Bodies (Maji)' },
        // Swamp — Wetland, R151 G219 B242
        swamp:             { fillColor: rgb(151, 219, 242), color: rgb(40, 120, 80),   label: 'Swamp (Ardhi Oevu)', pattern: 'wetland' },
        // Water Source — R64 G101 B235
        water_source:      { fillColor: rgb(151, 200, 242), color: rgb(64, 101, 235),  label: 'Water Source', pattern: 'water' },
        // Sand Beach — R255 G200 B10
        sand_beach:        { fillColor: rgb(255, 200, 10),  color: rgb(180, 140, 0),   label: 'Sand Beach' },
        // Cliff — R0 G0 B255
        cliff:             { fillColor: rgb(180, 180, 255), color: rgb(0, 0, 255),     label: 'Cliff', pattern: 'periglacial' },
        // Huduma za Jamii — Planning colour: RED
        services:          { fillColor: rgb(220, 20, 60),   color: rgb(140, 0, 30),    label: 'Huduma za Jamii' },
        communal:          { fillColor: rgb(250, 222, 17),  color: rgb(170, 140, 0),   label: 'Mixed Use / Ardhi ya Kawaida' },
        // Barabara — hakuna kwenye legend; tumia outline nyeusi juu ya cream
        transport:         { fillColor: rgb(220, 220, 220), color: rgb(80, 80, 80),    label: 'Road Reserve / Barabara' },
        other:             { fillColor: rgb(200, 200, 200), color: rgb(100, 100, 100), label: 'Other / Matumizi Mengine' }
    };

    // Alias za zamani (residential → settlement, pasture → grazing, n.k.)
    PALETTE.residential = PALETTE.settlement;
    PALETTE.urban = PALETTE.settlement;
    PALETTE.pasture = PALETTE.grazing;
    PALETTE.forest = PALETTE.open_forest;
    PALETTE.conservation = PALETTE.national_park;
    PALETTE.wetland = PALETTE.swamp;
    PALETTE.commercial = PALETTE.mixed;

    var TUMIZI_CODES = {
        '1':  { key: 'agriculture',      label: '1 — Agriculture (Kilimo)' },
        '2':  { key: 'settlement',       label: '2 — Settlement (Makazi)' },
        '3':  { key: 'open_forest',      label: '3 — Open Forest (Msitu)' },
        '4':  { key: 'grazing',          label: '4 — Grazing (Malisho)' },
        '5':  { key: 'water',            label: '5 — Water Bodies' },
        '6':  { key: 'swamp',            label: '6 — Swamp' },
        '7':  { key: 'mixed',            label: '7 — Mixed Use' },
        '8':  { key: 'transport',        label: '8 — Road / Infrastructure' },
        '9':  { key: 'mixed',            label: '9 — Mixed Use' },
        '10': { key: 'national_park',    label: '10 — Conservation' },
        '11': { key: 'industrial',       label: '11 — Industrial' },
        '12': { key: 'mining',           label: '12 — Mining' },
        '13': { key: 'services',         label: '13 — Huduma za Jamii' },
        '99': { key: 'other',            label: '99 — Other' },
        '0':  { key: 'other',            label: '0 — Other' }
    };

    var ALIASES = {
        settlement: [
            'settlement', 'residential', 'housing', 'house', 'homes', 'makazi', 'makao',
            'village settlement', 'makazi mtawanyiko', 'eneo la makazi', 'viwanja vya makazi',
            'nyumba', 'makazi ya vijijini', 'makazi ya kijiji', 'urban', 'built', 'builtup',
            'built-up', 'town', 'city', 'mji', 'miji'
        ],
        agriculture: [
            'agriculture', 'agric', 'agricultural', 'crop', 'crops', 'cultivated', 'cultivation',
            'farm', 'farming', 'kilimo', 'kilimo cha kienyeji', 'kilimo bora', 'kilimo cha biashara',
            'shamba', 'mashamba', 'arable', 'mazao', 'eneo la kilimo', 'ardhi ya kilimo'
        ],
        agric_settlement: [
            'agriculture and settlement', 'agric and settlement', 'kilimo makazi', 'makazi kilimo',
            'kilimo na makazi', 'agro residential', 'agro-residential'
        ],
        agric_irrigation: [
            'agric irrigation', 'agriculture irrigation', 'irrigation', 'irrigated',
            'kilimo cha umwagiliaji', 'umwagiliaji', 'irrigated agriculture'
        ],
        mixed: [
            'mixed', 'mixed use', 'mchanganyiko', 'matumizi mchanganyiko', 'multiple use'
        ],
        grazing: [
            'grazing', 'pasture', 'open pasture', 'rangeland', 'grassland', 'malisho',
            'malishoni', 'mifugo', 'malisho ya mifugo', 'eneo la malisho'
        ],
        forest_reserve: [
            'forest reserve', 'fr', 'hifadhi ya misitu', 'msitu wa hifadhi'
        ],
        open_forest: [
            'open forest', 'of', 'forest', 'forestry', 'woodland', 'misitu', 'msitu',
            'msitu wa kijiji', 'msitu wa asili', 'misitu ya asili', 'eneo la misitu'
        ],
        plantation: [
            'plantation', 'pl', 'msitu wa kupandwa', 'miti iliyopandwa', 'tree plantation'
        ],
        mangrove: [
            'mangrove', 'mangrove forest', 'mikoko', 'msitu wa mikoko'
        ],
        national_park: [
            'national park', 'np', 'mbuga ya taifa'
        ],
        game_controlled: [
            'game controlled area', 'gca', 'eneo la kudhibiti wanyama'
        ],
        game_reserve: [
            'game reserve', 'gr', 'mbuga ya wanyama', 'hifadhi ya wanyamapori'
        ],
        wma: [
            'wildlife management area', 'wma', 'eneo la usimamizi wa wanyamapori'
        ],
        land_bank: [
            'land bank', 'eneo la ardhi ya akiba', 'ardhi ya akiba', 'eneo la akiba', 'akiba'
        ],
        industrial: [
            'industrial', 'industry', 'factory', 'viwanda', 'kiwanda', 'eneo la viwanda'
        ],
        mining: [
            'mining', 'mine', 'madini', 'uchimbaji', 'machimbo', 'eneo la madini'
        ],
        quarry: [
            'quarry', 'machimbo ya mawe', 'kokoto'
        ],
        historic: [
            'historic', 'historic site', 'historical', 'eneo la kihistoria', 'magofu'
        ],
        water: [
            'water', 'water bodies', 'water body', 'river', 'lake', 'stream', 'pond',
            'maji', 'mto', 'ziwa', 'bwawa', 'hifadhi ya mto', 'eneo la mto'
        ],
        swamp: [
            'swamp', 'wetland', 'wetlands', 'marsh', 'oevu', 'ovu', 'ardhi oevu',
            'kinamasi', 'maeneo ya kinamasi'
        ],
        water_source: [
            'water source', 'spring', 'chanzo cha maji', 'kisimani', 'water intermittent'
        ],
        sand_beach: [
            'sand beach', 'beach', 'ufukwe', 'mchanga'
        ],
        cliff: [
            'cliff', 'mwamba', 'korongo'
        ],
        services: [
            'huduma', 'huduma za jamii', 'huduma za kijamii', 'social service', 'social services',
            'community service', 'public service', 'shule', 'zahanati', 'ofisi', 'eneo la huduma'
        ],
        communal: [
            'ardhi ya kawaida', 'communal', 'common land', 'open space', 'uwanja wa kijiji',
            'eneo la umma', 'public open space'
        ],
        transport: [
            'transport', 'road', 'railway', 'infrastructure', 'miundombinu', 'barabara',
            'hifadhi ya barabara', 'road reserve', 'right of way', 'row'
        ],
        other: [
            'matumizi mengine', 'mengine', 'nyingine', 'other', 'others', 'hakuna'
        ]
    };

    var FIELD_KEYS = [
        'tumiz', 'Tumiz', 'TUMIZ',
        'tumizi', 'TUMIZI', 'Tumizi',
        'tumizi_2', 'Tumizi_2', 'TUMIZI_2',
        'matumizi', 'Matumizi', 'MATUMIZI', 'matumizi_ardhi', 'MATUMIZI_ARDHI',
        'Matumizi_y', 'MATUMIZI_Y', 'Matumizi_1', 'MATUMIZI_1', 'Matumizi_Y',
        'land_use', 'LAND_USE', 'Land_Use', 'LandUse',
        'ainat', 'AINAT', 'aina', 'AINA', 'aina_tumizi', 'AINA_TUMIZI',
        'landuse_type', 'landuse', 'LANDUSE', 'Landuse', 'LU_CODE', 'LUCODE', 'lu_code',
        'class', 'CLASS', 'Class', 'class_name', 'CLASS_NAME', 'type', 'TYPE', 'Type',
        'category', 'CATEGORY', 'Category',
        'descr', 'DESCR', 'description', 'DESCRIPTION', 'name', 'NAME', 'lu_name', 'jina', 'JINA'
    ];

    var FALLBACK_FILLS = [
        rgb(255, 243, 20), rgb(0, 214, 104), rgb(227, 158, 0), rgb(0, 117, 37),
        rgb(144, 238, 144), rgb(250, 200, 200), rgb(215, 160, 250), rgb(255, 125, 0),
        rgb(151, 219, 242), rgb(250, 222, 17), rgb(109, 187, 67), rgb(64, 101, 235)
    ];
    var FALLBACK_STROKES = [
        rgb(180, 160, 0), rgb(0, 140, 70), rgb(160, 100, 0), rgb(0, 70, 20),
        rgb(60, 140, 60), rgb(180, 100, 100), rgb(140, 80, 180), rgb(180, 70, 0),
        rgb(70, 140, 180), rgb(170, 140, 0), rgb(60, 120, 35), rgb(40, 60, 180)
    ];

    var legendControl = null;

    function stripText(raw) {
        return String(raw || '')
            .toLowerCase()
            .trim()
            .replace(/[_\-]+/g, ' ')
            .replace(/\s+/g, ' ');
    }

    function parseTumiziCode(raw) {
        if (raw == null || raw === '') return null;
        var str = String(raw).trim();
        var numMatch = str.match(/^0*(\d+)(?:\.0+)?$/);
        if (numMatch) return numMatch[1];
        var leadMatch = str.match(/^0*(\d+)\s*[-.:]\s*\w+/i);
        if (leadMatch) return leadMatch[1];
        return null;
    }

    function hashColorIndex(text) {
        var s = stripText(text);
        var h = 0;
        for (var i = 0; i < s.length; i++) {
            h = ((h << 5) - h) + s.charCodeAt(i);
            h |= 0;
        }
        return Math.abs(h) % FALLBACK_FILLS.length;
    }

    function paletteForKey(key, raw) {
        if (key && PALETTE[key] && key !== 'other') {
            return PALETTE[key];
        }
        if (raw != null && String(raw).trim() !== '') {
            var idx = hashColorIndex(raw);
            return {
                color: FALLBACK_STROKES[idx],
                fillColor: FALLBACK_FILLS[idx],
                label: String(raw).trim()
            };
        }
        return PALETTE.other;
    }

    function getDisplayLabel(raw, key) {
        var code = parseTumiziCode(raw);
        if (code && TUMIZI_CODES[code]) {
            return TUMIZI_CODES[code].label;
        }
        if (raw != null && String(raw).trim() !== '') {
            return String(raw).trim();
        }
        return (PALETTE[key] || PALETTE.other).label;
    }

    function normalizeKey(raw) {
        if (raw == null || raw === '') return 'other';

        var code = parseTumiziCode(raw);
        if (code && TUMIZI_CODES[code]) {
            return TUMIZI_CODES[code].key;
        }

        var s = stripText(raw);
        if (!s) return 'other';

        if (PALETTE[s]) return s;

        var canon, list, i;
        for (canon in ALIASES) {
            list = ALIASES[canon];
            for (i = 0; i < list.length; i++) {
                if (s === list[i]) return canon;
            }
        }

        var best = null;
        var bestLen = 0;
        for (canon in ALIASES) {
            list = ALIASES[canon];
            for (i = 0; i < list.length; i++) {
                var alias = list[i];
                if (alias.length < 3) continue;
                if ((s.indexOf(alias) !== -1 || alias.indexOf(s) !== -1) && alias.length > bestLen) {
                    best = canon;
                    bestLen = alias.length;
                }
            }
        }
        if (best) return best;

        for (var key in PALETTE) {
            if (key === 'other') continue;
            if (s === key || s.indexOf(key.replace(/_/g, ' ')) !== -1) return key;
        }

        return 'other';
    }

    function extractLanduseValue(properties) {
        if (!properties) return null;
        var i, k, pk;
        for (i = 0; i < FIELD_KEYS.length; i++) {
            k = FIELD_KEYS[i];
            if (properties[k] != null && String(properties[k]).trim() !== '') {
                return properties[k];
            }
        }
        for (pk in properties) {
            if (!Object.prototype.hasOwnProperty.call(properties, pk)) continue;
            if (/^(fid|objectid|id|shape|area|ha|acres|length|perimeter)$/i.test(pk)) continue;
            if (/land|use|class|type|category|matumizi|tumizi|tumiz|ainat|aina|lu_|luc/i.test(pk)) {
                var v = properties[pk];
                if (v != null && String(v).trim() !== '') return v;
            }
        }
        return null;
    }

    function styleForFeature(feature) {
        var props = feature && feature.properties ? feature.properties : {};
        var raw = extractLanduseValue(props);
        var key = normalizeKey(raw);
        var pal = paletteForKey(key, raw);
        var style = {
            color: pal.color,
            fillColor: pal.fillColor,
            weight: 1.5,
            fillOpacity: 0.75,
            opacity: 0.95
        };
        // Patterns za legend: hatch / scrub → dash outline ili kutofautisha
        if (pal.pattern === 'hatch' || pal.pattern === 'scrub' || pal.pattern === 'wetland') {
            style.dashArray = '4,3';
            style.fillOpacity = 0.65;
        } else if (pal.pattern === 'pasture' || pal.pattern === 'gravel') {
            style.fillOpacity = 0.7;
        }
        return style;
    }

    function categoriesInGeoJSON(geojson) {
        var found = {};
        var feats = (geojson && geojson.features) ? geojson.features : [];
        feats.forEach(function(f) {
            var raw = extractLanduseValue(f.properties || {});
            var key = normalizeKey(raw);
            var code = parseTumiziCode(raw);
            var groupKey = code
                ? ('code:' + code)
                : ('raw:' + stripText(raw || key));
            if (!found[groupKey]) {
                found[groupKey] = {
                    key: key,
                    label: getDisplayLabel(raw, key),
                    count: 0,
                    rawSample: raw,
                    code: code,
                    palette: paletteForKey(key, raw)
                };
            }
            found[groupKey].count += 1;
        });
        return Object.keys(found).map(function(k) { return found[k]; })
            .sort(function(a, b) {
                if (a.code && b.code) return parseInt(a.code, 10) - parseInt(b.code, 10);
                if (a.code) return -1;
                if (b.code) return 1;
                return b.count - a.count;
            });
    }

    function buildPopupHtml(feature) {
        var props = feature.properties || {};
        var raw = extractLanduseValue(props);
        var key = normalizeKey(raw);
        var pal = paletteForKey(key, raw);
        var displayLabel = getDisplayLabel(raw, key);
        var planningLabel = (PALETTE[key] || PALETTE.other).label;
        var html = '<div style="min-width:170px;font-size:12px;">';
        html += '<b>Matumizi ya Ardhi</b><br>';
        html += '<span style="display:inline-block;width:14px;height:14px;background:' + pal.fillColor +
            ';border:1px solid ' + pal.color + ';margin-right:4px;vertical-align:middle;"></span>';
        html += '<b>' + displayLabel + '</b>';
        if (planningLabel && planningLabel !== displayLabel) {
            html += '<br><small>Planning: ' + planningLabel + '</small>';
        }
        if (props.kijiji) html += '<br>Kijiji: ' + props.kijiji;
        if (props.kata) html += '<br>Kata: ' + props.kata;
        if (props.wilaya) html += '<br>Wilaya: ' + props.wilaya;
        if (props.area_ha != null) html += '<br>Eneo: ' + props.area_ha + ' ha';
        html += '</div>';
        return html;
    }

    function removeLegend(map) {
        if (legendControl && map) {
            map.removeControl(legendControl);
        }
        legendControl = null;
    }

    function addLegend(map, geojson) {
        removeLegend(map);
        if (!map) return;

        var cats = categoriesInGeoJSON(geojson);
        if (!cats.length) return;

        legendControl = L.control({ position: 'bottomright' });
        legendControl.onAdd = function() {
            var div = L.DomUtil.create('div', 'legend landuse-upload-legend');
            var html = '<strong>Planning Colours — Matumizi</strong><br>';
            cats.forEach(function(c) {
                var pal = c.palette || paletteForKey(c.key, c.rawSample);
                html += '<div class="lu-leg-item">' +
                    '<span class="lu-swatch" style="background:' + pal.fillColor + ';border-color:' + pal.color + ';"></span>' +
                    c.label + ' <small>(' + c.count + ')</small></div>';
            });
            div.innerHTML = html;
            return div;
        };
        legendControl.addTo(map);
    }

    return {
        PALETTE: PALETTE,
        TUMIZI_CODES: TUMIZI_CODES,
        normalizeKey: normalizeKey,
        parseTumiziCode: parseTumiziCode,
        getDisplayLabel: getDisplayLabel,
        paletteForKey: paletteForKey,
        extractLanduseValue: extractLanduseValue,
        styleForFeature: styleForFeature,
        buildPopupHtml: buildPopupHtml,
        categoriesInGeoJSON: categoriesInGeoJSON,
        addLegend: addLegend,
        removeLegend: removeLegend
    };
})();
