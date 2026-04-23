"""テストデータを作成するスクリプト"""
from app import create_app
from app.models.crop import Crop
from app.models.variety import Variety
from app.models.location import Location
from app.models.planting import Planting

app = create_app()

with app.app_context():
    # 作物を登録（品種情報は別テーブルへ）
    print("=== 作物を登録中 ===")
    crops_data = [
        {
            'name': 'トマト',
            'crop_type': 'トマト',
            'notes': ('## 植え付け時期\n4月〜5月\n\n'
                      '## 収穫時期\n7月〜9月\n\n'
                      '## 特性\n日当たりの良い場所で栽培'),
        },
        {
            'name': 'なす',
            'crop_type': 'なす',
            'notes': ('## 植え付け時期\n5月〜6月\n\n'
                      '## 収穫時期\n7月〜10月\n\n'
                      '## 特性\n水を多めに与える'),
        },
        {
            'name': 'きゅうり',
            'crop_type': 'きゅうり',
            'notes': ('## 植え付け時期\n5月〜6月\n\n'
                      '## 収穫時期\n6月〜9月\n\n'
                      '## 特性\nネット栽培がおすすめ'),
        },
    ]

    crop_ids = {}
    for data in crops_data:
        crop_id = Crop.create(data)
        crop_ids[data['name']] = crop_id
        print(f"[OK] 作物「{data['name']}」を登録しました (ID: {crop_id})")

    # 品種を登録
    print("\n=== 品種を登録中 ===")
    varieties_data = [
        {'crop_id': crop_ids['トマト'], 'name': 'アイコ', 'notes': '## 特性\n甘みが強く皮が薄い'},
        {'crop_id': crop_ids['トマト'], 'name': '桃太郎', 'notes': '## 特性\n完熟で出荷できる大玉品種'},
        {'crop_id': crop_ids['なす'], 'name': '千両二号', 'notes': '## 特性\n標準的な長なす'},
        {'crop_id': crop_ids['きゅうり'], 'name': '夏すずみ', 'notes': '## 特性\n病気に強い'},
    ]

    variety_ids = {}
    for data in varieties_data:
        variety_id = Variety.create(data)
        variety_ids[data['name']] = variety_id
        print(f"[OK] 品種「{data['name']}」を登録しました (ID: {variety_id})")

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

    # 作物を植え付け（品種指定あり/なし 混在）
    print("\n=== 作物を植え付け中 ===")
    planting_data = [
        {
            'location_id': location_ids[0],
            'crop_id': crop_ids['トマト'],
            'variety_id': variety_ids['アイコ'],
            'planted_date': '2024-05-15',
            'quantity': 5,
            'notes': '苗から植え付け'
        },
        {
            'location_id': location_ids[0],
            'crop_id': crop_ids['なす'],
            'variety_id': variety_ids['千両二号'],
            'planted_date': '2024-05-20',
            'quantity': 3,
            'notes': '苗から植え付け'
        },
        {
            'location_id': location_ids[1],
            'crop_id': crop_ids['きゅうり'],
            'variety_id': None,  # 品種未指定も可能
            'planted_date': '2024-05-25',
            'quantity': 2,
            'notes': 'プランター栽培（品種未指定）'
        }
    ]

    for data in planting_data:
        lc_id = Planting.plant(data)
        crop = Crop.get_by_id(data['crop_id'])
        location = Location.get_by_id(data['location_id'])
        print(f"[OK] 「{location['name']}」に「{crop['name']}」を植え付けました")

    # 統計情報を表示
    print("\n=== 統計情報 ===")
    print(f"登録作物数: {Crop.count()}")
    print(f"登録品種数: {Variety.count()}")
    print(f"登録場所数: {Location.count()}")
    print(f"栽培中作物数: {Planting.count_active()}")

    print("\n[完了] テストデータの作成が完了しました！")
    print("ブラウザで http://localhost:5000 にアクセスしてアプリを確認してください。")
