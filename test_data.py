"""テストデータを作成するスクリプト"""
from app import create_app
from app.models.crop import Crop
from app.models.location import Location
from app.models.location_crop import LocationCrop

app = create_app()

with app.app_context():
    # 作物を登録
    print("=== 作物を登録中 ===")
    crops_data = [
        {
            'name': 'ミニトマト',
            'crop_type': 'トマト',
            'variety': 'アイコ',
            'planting_season': '4月～5月',
            'harvest_season': '7月～9月',
            'notes': '日当たりの良い場所で栽培'
        },
        {
            'name': '丸なす',
            'crop_type': 'なす',
            'variety': '千両二号',
            'planting_season': '5月～6月',
            'harvest_season': '7月～10月',
            'notes': '水を多めに与える'
        },
        {
            'name': 'きゅうり',
            'crop_type': 'きゅうり',
            'variety': '夏すずみ',
            'planting_season': '5月～6月',
            'harvest_season': '6月～9月',
            'notes': 'ネット栽培がおすすめ'
        }
    ]

    crop_ids = []
    for data in crops_data:
        crop_id = Crop.create(data)
        crop_ids.append(crop_id)
        print(f"[OK] 作物「{data['name']}」を登録しました (ID: {crop_id})")

    # 場所を登録
    print("\n=== 場所を登録中 ===")
    locations_data = [
        {
            'name': '南側の畑',
            'location_type': '畑',
            'area_size': 10.5,
            'sun_exposure': '全日',
            'notes': 'メインの栽培場所'
        },
        {
            'name': 'ベランダプランター1',
            'location_type': 'プランター',
            'area_size': 0.3,
            'sun_exposure': '半日',
            'notes': 'ベランダ左側'
        }
    ]

    location_ids = []
    for data in locations_data:
        location_id = Location.create(data)
        location_ids.append(location_id)
        print(f"[OK] 場所「{data['name']}」を登録しました (ID: {location_id})")

    # 作物を植え付け
    print("\n=== 作物を植え付け中 ===")
    planting_data = [
        {
            'location_id': location_ids[0],
            'crop_id': crop_ids[0],
            'planted_date': '2024-05-15',
            'quantity': 5,
            'notes': '苗から植え付け'
        },
        {
            'location_id': location_ids[0],
            'crop_id': crop_ids[1],
            'planted_date': '2024-05-20',
            'quantity': 3,
            'notes': '苗から植え付け'
        },
        {
            'location_id': location_ids[1],
            'crop_id': crop_ids[2],
            'planted_date': '2024-05-25',
            'quantity': 2,
            'notes': 'プランター栽培'
        }
    ]

    for data in planting_data:
        lc_id = LocationCrop.plant(data)
        crop = Crop.get_by_id(data['crop_id'])
        location = Location.get_by_id(data['location_id'])
        print(f"[OK] 「{location['name']}」に「{crop['name']}」を植え付けました")

    # 統計情報を表示
    print("\n=== 統計情報 ===")
    print(f"登録作物数: {Crop.count()}")
    print(f"登録場所数: {Location.count()}")
    print(f"栽培中作物数: {LocationCrop.count_active()}")

    print("\n[完了] テストデータの作成が完了しました！")
    print("ブラウザで http://localhost:5000 にアクセスしてアプリを確認してください。")
