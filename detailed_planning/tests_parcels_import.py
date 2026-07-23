"""Tests for parcel import and GeoJSON API (WGS84)."""
from __future__ import annotations

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import Client, SimpleTestCase, TestCase

from detailed_planning.models import PlanningParcel
from detailed_planning.services import (
    _canonical_import_district,
    _geom_to_wgs84_dict,
    _infer_village_from_name,
    compute_is_identified,
    geojson_to_multipolygon,
    import_parcels_from_geojson,
    normalize_import_district,
)


class DistrictAliasTests(SimpleTestCase):
    def test_songea_includes_madaba_alias(self):
        from dashboard.boundary_service import _district_search_names

        names = {n.lower() for n in _district_search_names('Songea')}
        self.assertIn('songea', names)
        self.assertIn('madaba', names)

    def test_madaba_includes_songea_alias(self):
        from dashboard.boundary_service import _district_search_names

        names = {n.lower() for n in _district_search_names('Madaba')}
        self.assertIn('songea', names)
        self.assertIn('madaba', names)


class ParcelGeoJsonApiTests(TestCase):
    databases = {'default', 'detailed_planning'}

    def test_songea_alias_returns_mwande_parcels(self):
        count = PlanningParcel.objects.filter(
            region_name__iexact='Ruvuma',
            district_name__iexact='Madaba',
            ward_name__iexact='Matetereka',
            village_name__iexact='Mwande',
        ).exclude(geom__isnull=True).count()
        if count == 0:
            self.skipTest('Hakuna viwanja vya Mwande kwenye DB ya majaribio')

        client = Client()
        resp = client.get(
            '/api/planning/parcels/geojson/',
            {
                'region': 'Ruvuma',
                'district': 'Songea',
                'ward': 'Matetereka',
                'village': 'Mwande',
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['features']), count)
        ring = data['features'][0]['geometry']['coordinates'][0][0]
        self.assertTrue(30 <= ring[0] <= 45)
        self.assertTrue(-12 <= ring[1] <= 0)

    def test_villages_api_lists_mwande_under_songea(self):
        if not PlanningParcel.objects.filter(village_name__iexact='Mwande').exists():
            self.skipTest('Hakuna viwanja vya Mwande kwenye DB ya majaribio')

        client = Client()
        resp = client.get('/api/planning/villages/Ruvuma/Songea/Matetereka/')
        self.assertEqual(resp.status_code, 200)
        names = {item['name'] for item in resp.json()}
        self.assertIn('Mwande', names)

    def test_ward_level_returns_all_village_parcels(self):
        ward_total = PlanningParcel.objects.filter(
            region_name__iexact='Ruvuma',
            ward_name__iexact='Matetereka',
        ).exclude(geom__isnull=True).count()
        if ward_total == 0:
            self.skipTest('Hakuna viwanja kwenye DB ya majaribio')

        client = Client()
        resp = client.get(
            '/api/planning/parcels/geojson/',
            {
                'region': 'Ruvuma',
                'district': 'Songea',
                'ward': 'Matetereka',
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['meta']['total_matching'], ward_total)
        self.assertEqual(data['meta']['returned'], ward_total)
        self.assertEqual(len(data['features']), ward_total)

    def test_geojson_has_no_arbitrary_limit(self):
        """Hakuna kikomo cha [:2000] — idadi ya features = idadi ya DB."""
        from detailed_planning.views import _location_filter

        flt = _location_filter('Ruvuma', 'Songea', 'Matetereka')
        db_count = PlanningParcel.objects.filter(flt).exclude(geom__isnull=True).count()
        if db_count == 0:
            self.skipTest('Hakuna viwanja kwenye DB ya majaribio')

        client = Client()
        resp = client.get(
            '/api/planning/parcels/geojson/',
            {'region': 'Ruvuma', 'district': 'Songea', 'ward': 'Matetereka'},
        )
        data = resp.json()
        self.assertEqual(len(data['features']), db_count)
        self.assertEqual(data['meta']['returned'], db_count)

    def test_parcels_list_returns_total_without_500_cap(self):
        flt_count = PlanningParcel.objects.filter(
            region_name__iexact='Ruvuma',
            ward_name__iexact='Matetereka',
        ).count()
        if flt_count == 0:
            self.skipTest('Hakuna viwanja kwenye DB ya majaribio')

        client = Client()
        resp = client.get(
            '/api/planning/parcels/',
            {'region': 'Ruvuma', 'district': 'Songea', 'ward': 'Matetereka'},
        )
        data = resp.json()
        self.assertEqual(data['total'], flt_count)
        self.assertEqual(data['count'], flt_count)


class DataPortalApiTests(TestCase):
    databases = {'default', 'detailed_planning'}

    def test_stats_uses_parcel_counts_with_songea_alias(self):
        flt_count = PlanningParcel.objects.filter(
            region_name__iexact='Ruvuma',
            ward_name__iexact='Matetereka',
        ).count()
        if flt_count == 0:
            self.skipTest('Hakuna viwanja kwenye DB ya majaribio')

        client = Client()
        resp = client.get(
            '/api/planning/stats/',
            {'region': 'Ruvuma', 'district': 'Songea', 'ward': 'Matetereka'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_parcels'], flt_count)
        self.assertIn('identified_parcels', data)
        self.assertIn('unidentified_parcels', data)
        self.assertIn('total_landowners', data)
        self.assertIn('by_gender', data)
        self.assertIn('by_age', data)
        self.assertIn('special_groups', data)
        self.assertIn('male', data['by_gender'])
        self.assertIn('female', data['by_gender'])
        self.assertIn('adult', data['by_age'])
        self.assertIn('child_under_18', data['by_age'])
        self.assertIn('total_mpango_kinaa', data)

    def test_ccro_landowners_includes_shapefile_fields(self):
        parcel = PlanningParcel.objects.filter(
            region_name__iexact='Ruvuma',
            ward_name__iexact='Matetereka',
        ).first()
        if not parcel:
            self.skipTest('Hakuna viwanja kwenye DB ya majaribio')

        client = Client()
        resp = client.get(
            '/api/planning/ccro/landowners/',
            {
                'region': 'Ruvuma',
                'district': 'Songea',
                'ward': 'Matetereka',
                'all': '1',
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data['total'], 0)
        row = data['landowners'][0]
        for field in (
            'parcel_number', 'owner_name', 'pid', 'claim_no', 'parties',
            'land_use', 'ownership_type', 'neighbor_north', 'neighbor_south',
            'shapefile_name', 'source_layer', 'notes',
        ):
            self.assertIn(field, row)

    def test_ccro_response_includes_source_summary(self):
        if not PlanningParcel.objects.exists():
            self.skipTest('Hakuna viwanja kwenye DB ya majaribio')

        parcel = PlanningParcel.objects.first()
        client = Client()
        resp = client.get(
            '/api/planning/ccro/landowners/',
            {
                'region': parcel.region_name,
                'all': '1',
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data_source'], 'planning_parcels')
        self.assertIn('sources', data)
        self.assertIn('shapefile_names', data['sources'])

    def test_stats_data_source_is_planning_parcels(self):
        if not PlanningParcel.objects.exists():
            self.skipTest('Hakuna viwanja kwenye DB ya majaribio')

        parcel = PlanningParcel.objects.first()
        client = Client()
        resp = client.get(
            '/api/planning/stats/',
            {'region': parcel.region_name},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data_source'], 'planning_parcels')
        self.assertEqual(data['total_parcels'], PlanningParcel.objects.filter(
            region_name__iexact=parcel.region_name,
        ).count())

    def test_ccro_search_by_parties(self):
        parcel = PlanningParcel.objects.exclude(parties__isnull=True).exclude(parties='').first()
        if not parcel or not parcel.parties:
            self.skipTest('Hakuna parties kwenye DB ya majaribio')

        snippet = parcel.parties[:8]
        client = Client()
        resp = client.get(
            '/api/planning/ccro/landowners/',
            {
                'region': parcel.region_name,
                'district': parcel.district_name,
                'search': snippet,
                'all': '1',
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.json()['total'], 0)


class ParcelIdentificationTests(SimpleTestCase):
    def test_empty_parcel_is_unidentified(self):
        self.assertFalse(compute_is_identified())

    def test_owner_name_is_identified(self):
        self.assertTrue(compute_is_identified(owner_name='John Doe'))

    def test_parties_is_identified(self):
        self.assertTrue(compute_is_identified(parties='Jane & John'))

    def test_claim_no_is_identified(self):
        self.assertTrue(compute_is_identified(claim_no='CCRO-001'))

    def test_pid_without_other_fields_is_identified(self):
        self.assertTrue(compute_is_identified(pid='12345'))

    def test_land_use_is_identified(self):
        self.assertTrue(compute_is_identified(land_use='Kilimo'))

    def test_explicit_unidentified_flag(self):
        self.assertFalse(compute_is_identified(raw='haijatambuliwa', owner_name='Someone'))

    def test_district_alias_normalization(self):
        self.assertEqual(normalize_import_district('Madaba', 'Songea'), 'Songea')
        self.assertEqual(normalize_import_district('Songea', 'Madaba'), 'Madaba')

    def test_canonical_import_district_prefers_upload(self):
        self.assertEqual(_canonical_import_district('Songea', 'Madaba'), 'Songea')
        self.assertEqual(_canonical_import_district('Madaba', 'Songea'), 'Madaba')


class ParcelImportUnitTests(SimpleTestCase):
    def test_infer_village_from_filename(self):
        self.assertEqual(_infer_village_from_name('igawisenga.zip'), 'Igawisenga')
        self.assertEqual(_infer_village_from_name('Mwande_parcels.shp'), 'Mwande')

    def test_pick_village_from_kijiji_column(self):
        from detailed_planning.services import _pick_village_from_props, resolve_village_for_feature
        self.assertEqual(_pick_village_from_props({'Kijiji': 'Igawisenga'}), 'Igawisenga')
        self.assertEqual(
            resolve_village_for_feature(
                {'village': 'mwande'},
                known_villages=['Mwande', 'Igawisenga'],
            ),
            'Mwande',
        )

    def test_geojson_to_multipolygon_from_wgs84(self):
        geom_json = {
            'type': 'Polygon',
            'coordinates': [[
                [35.75, -9.85],
                [35.751, -9.85],
                [35.751, -9.849],
                [35.75, -9.849],
                [35.75, -9.85],
            ]],
        }
        geom = geojson_to_multipolygon(geom_json, source_srid=4326)
        self.assertIsNotNone(geom)
        self.assertEqual(geom.srid, 32736)

    def test_wgs84_dict_returns_lon_lat(self):
        poly = Polygon(
            ((500000, 9000000), (501000, 9000000), (501000, 9001000), (500000, 9001000), (500000, 9000000)),
            srid=32736,
        )
        mp = MultiPolygon(poly, srid=32736)
        out = _geom_to_wgs84_dict(mp)
        self.assertIsNotNone(out)
        ring = out['coordinates'][0][0]
        self.assertTrue(-90 <= ring[0][1] <= 0)
        self.assertTrue(30 <= ring[0][0] <= 45)


class ParcelImportDbTests(TestCase):
    databases = {'default', 'detailed_planning'}

    def test_import_skipped_when_ward_missing(self):
        fc = {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [35.75, -9.85], [35.751, -9.85], [35.751, -9.849],
                        [35.75, -9.849], [35.75, -9.85],
                    ]],
                },
                'properties': {},
            }],
        }
        result = import_parcels_from_geojson(
            fc,
            region='Ruvuma',
            district='Songea',
            ward=None,
            shapefile_name='unknown.zip',
        )
        self.assertEqual(result['skipped'], 1)

    def test_import_infers_village_from_filename_at_ward_level(self):
        fc = {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [35.75, -9.85], [35.751, -9.85], [35.751, -9.849],
                        [35.75, -9.849], [35.75, -9.85],
                    ]],
                },
                'properties': {},
            }],
        }
        result = import_parcels_from_geojson(
            fc,
            region='Ruvuma',
            district='Songea',
            ward='Matetereka',
            shapefile_name='mwande_test.zip',
        )
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['village'], 'Mwande')
        PlanningParcel.objects.filter(
            village_name='Mwande',
            ward_name='Matetereka',
            district_name='Songea',
            region_name='Ruvuma',
        ).delete()


class VillagePlanDeduplicationTests(TestCase):
    databases = {'default', 'detailed_planning'}

    def setUp(self):
        from detailed_planning.models import VillageDetailedPlan

        VillageDetailedPlan.objects.filter(
            region_name__iexact='Ruvuma',
            ward_name__iexact='Matetereka',
            village_name__iexact='Mwande',
        ).delete()

    def test_merge_duplicate_mwande_madaba_songea(self):
        from detailed_planning.models import VillageDetailedPlan
        from detailed_planning.services import (
            deduplicate_village_plan_list,
            merge_duplicate_village_plans,
        )

        VillageDetailedPlan.objects.create(
            region_name='Ruvuma',
            district_name='Madaba',
            ward_name='Matetereka',
            village_name='Mwande',
            plan_status='draft',
        )
        VillageDetailedPlan.objects.create(
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='Matetereka',
            village_name='Mwande',
            plan_status='prepared',
        )

        merged = merge_duplicate_village_plans(
            region='Ruvuma',
            district='Songea',
            ward='Matetereka',
            prefer_district='Songea',
        )
        self.assertEqual(merged, 1)
        self.assertEqual(
            VillageDetailedPlan.objects.filter(
                region_name__iexact='Ruvuma',
                ward_name__iexact='Matetereka',
                village_name__iexact='Mwande',
            ).count(),
            1,
        )

    def test_api_village_plans_returns_single_mwande(self):
        from detailed_planning.models import VillageDetailedPlan

        VillageDetailedPlan.objects.create(
            region_name='Ruvuma',
            district_name='Madaba',
            ward_name='Matetereka',
            village_name='Mwande',
            plan_status='draft',
        )
        VillageDetailedPlan.objects.create(
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='Matetereka',
            village_name='Mwande',
            plan_status='prepared',
        )

        client = Client()
        resp = client.get(
            '/api/planning/village-plans/',
            {'region': 'Ruvuma', 'district': 'Songea', 'ward': 'Matetereka'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        mwande = [p for p in data['plans'] if p['village_name'].lower() == 'mwande']
        self.assertEqual(len(mwande), 1)
        self.assertEqual(data['total_mpango_kinaa'], len(data['plans']))

    def test_deduplicate_prefers_filter_district(self):
        from detailed_planning.models import VillageDetailedPlan
        from detailed_planning.services import deduplicate_village_plan_list

        madaba = VillageDetailedPlan.objects.create(
            region_name='Ruvuma',
            district_name='Madaba',
            ward_name='Matetereka',
            village_name='Mwande',
            plan_status='draft',
        )
        songea = VillageDetailedPlan.objects.create(
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='Matetereka',
            village_name='Mwande',
            plan_status='prepared',
        )

        deduped = deduplicate_village_plan_list(
            [madaba, songea],
            prefer_district='Madaba',
        )
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].district_name, 'Madaba')
