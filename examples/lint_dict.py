from stac_check.lint import Linter

file = {
    "stac_version": "1.0.0",
    "stac_extensions": [],
    "type": "Feature",
    "id": "20201211_223832_CS2",
    "bbox": [
        172.91173669923782,
        1.3438851951615003,
        172.95469614953714,
        1.3690476620161975
    ],
    "geometry": {
        "type": "Polygon",
        "coordinates": [
        [
            [
            172.91173669923782,
            1.3438851951615003
            ],
            [
            172.95469614953714,
            1.3438851951615003
            ],
            [
            172.95469614953714,
            1.3690476620161975
            ],
            [
            172.91173669923782,
            1.3690476620161975
            ],
            [
            172.91173669923782,
            1.3438851951615003
            ]
        ]
        ]
    },
    "properties": {
        "title": "Core Item",
        "description": "A sample STAC Item that includes examples of all common metadata",
        "datetime": None,
        "start_datetime": "2020-12-11T22:38:32.125Z",
        "end_datetime": "2020-12-11T22:38:32.327Z",
        "created": "2020-12-12T01:48:13.725Z",
        "updated": "2020-12-12T01:48:13.725Z",
        "platform": "cool_sat1",
        "instruments": [
        "cool_sensor_v1"
        ],
        "constellation": "ion",
        "mission": "collection 5624",
        "gsd": 0.512
    },
    "collection": "simple-collection",
    "links": [
        {
        "rel": "collection",
        "href": "./collection.json",
        "type": "application/json",
        "title": "Simple Example Collection"
        },
        {
        "rel": "root",
        "href": "./collection.json",
        "type": "application/json",
        "title": "Simple Example Collection"
        },
        {
        "rel": "parent",
        "href": "./collection.json",
        "type": "application/json",
        "title": "Simple Example Collection"
        },
        {
        "rel": "alternate",
        "type": "text/html",
        "href": "http://remotedata.io/catalog/20201211_223832_CS2/index.html",
        "title": "HTML version of this STAC Item"
        }
    ],
    "assets": {
        "analytic": {
        "href": "https://storage.googleapis.com/open-cogs/stac-examples/20201211_223832_CS2_analytic.tif",
        "type": "image/tiff; application=geotiff; profile=cloud-optimized",
        "title": "4-Band Analytic",
        "roles": [
            "data"
        ]
        },
        "thumbnail": {
        "href": "https://storage.googleapis.com/open-cogs/stac-examples/20201211_223832_CS2.jpg",
        "title": "Thumbnail",
        "type": "image/png",
        "roles": [
            "thumbnail"
        ]
        },
        "visual": {
        "href": "https://storage.googleapis.com/open-cogs/stac-examples/20201211_223832_CS2.tif",
        "type": "image/tiff; application=geotiff; profile=cloud-optimized",
        "title": "3-Band Visual",
        "roles": [
            "visual"
        ]
        },
        "udm": {
        "href": "https://storage.googleapis.com/open-cogs/stac-examples/20201211_223832_CS2_analytic_udm.tif",
        "title": "Unusable Data Mask",
        "type": "image/tiff; application=geotiff;"
        },
        "json-metadata": {
        "href": "http://remotedata.io/catalog/20201211_223832_CS2/extended-metadata.json",
        "title": "Extended Metadata",
        "type": "application/json",
        "roles": [
            "metadata"
        ]
        },
        "ephemeris": {
        "href": "http://cool-sat.com/catalog/20201211_223832_CS2/20201211_223832_CS2.EPH",
        "title": "Satellite Ephemeris Metadata"
        }
    }
}
linter = Linter(file, assets=True)

print(f"valid: {linter.valid_stac}")
print(f"error_type: {linter.error_type}")
print(f"error_msg: {linter.error_msg}")
print(f"schema: {linter.schema}")
print(f"file_name: {linter.file_name}")
print("------")
for k,v in linter.create_best_practices_dict().items():
    print(k,":",v)
