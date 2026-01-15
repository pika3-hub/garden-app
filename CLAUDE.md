# CLAUDE.md - AI Assistant Guide for Garden Management App

This document provides comprehensive guidance for AI assistants (like Claude) working with this codebase. It covers architecture, conventions, workflows, and best practices.

## Project Overview

**Name:** 家庭菜園管理アプリ (Home Garden Management App)
**Type:** Flask-based Web Application
**Language:** Python 3.12 with Japanese UI
**Database:** SQLite
**Purpose:** Manage home garden cultivation tracking with visual canvas layout, diary entries, and crop-location relationships

### Core Features
- **Crop Management:** CRUD operations for crop types, varieties, and characteristics
- **Location Management:** CRUD for garden locations (gardens, planters) with image support
- **Canvas Editor:** Visual garden layout designer using Fabric.js (drag-drop crops, shapes, text)
- **Planting Tracking:** Link crops to locations with status tracking (active/harvested/removed)
- **Diary System:** Cultivation diary with multi-entity relationships and image attachments
- **Image Support:** Upload/manage images for crops, locations, and diary entries (max 16MB)
- **Search & Filter:** Keyword search across entities, date-range filtering for diary
- **Dashboard:** Statistics and recent activity overview

---

## Quick Reference

### Project Structure
```
garden-app/
├── app/                      # Main application package
│   ├── __init__.py          # Flask factory pattern
│   ├── config.py            # Environment-based configuration
│   ├── database.py          # SQLite connection management
│   ├── schema.sql           # Initial database schema
│   ├── models/              # Data models (static method pattern)
│   │   ├── crop.py
│   │   ├── location.py
│   │   ├── location_crop.py # Many-to-many relationship
│   │   └── diary.py
│   ├── routes/              # Flask blueprints
│   │   ├── crop_routes.py
│   │   ├── location_routes.py
│   │   └── diary_routes.py
│   ├── utils/               # Utilities
│   │   ├── upload.py        # Image upload helpers
│   │   └── migration.py     # Migration utilities
│   ├── migrations/          # Database migrations (incremental SQL)
│   ├── templates/           # Jinja2 templates
│   │   ├── base.html        # Base layout with navbar
│   │   ├── index.html       # Dashboard
│   │   ├── crops/           # Crop templates
│   │   ├── locations/       # Location templates (+ canvas.html)
│   │   └── diary/           # Diary templates
│   └── static/              # Static assets
│       ├── css/             # Bootstrap customization
│       ├── js/              # Canvas editor, utilities
│       └── uploads/         # User images (crops/, locations/, diary/)
├── instance/                # Flask instance folder (garden.db)
├── run.py                   # Application launcher
├── test_data.py             # Test data seeding
└── pyproject.toml           # Project metadata (uv package manager)
```

### Key Commands
```bash
# Setup
uv sync                           # Install dependencies

# Database
uv run python -c "from app import create_app; from app.database import init_db; app = create_app(); init_db(app)"

# Run
uv run python run.py              # Start dev server (localhost:5000)

# Test data
uv run python test_data.py        # Seed sample data
```

---

## Architecture Patterns

### 1. Flask Application Factory Pattern

**File:** `app/__init__.py`

```python
def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Register blueprints
    from app.routes import crop_routes, location_routes, diary_routes
    app.register_blueprint(crop_routes.bp)

    # Database teardown
    app.teardown_appcontext(close_db)

    return app
```

**Key Points:**
- Environment-based config selection (development/production/testing)
- Blueprint registration for modular routes
- Database connection cleanup via teardown

### 2. Static Method Model Pattern

**NO ORM - Direct SQL with static methods**

```python
class Crop:
    @staticmethod
    def get_all():
        db = get_db()
        rows = db.execute('SELECT * FROM crops ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def create(data):
        db = get_db()
        db.execute('''INSERT INTO crops (...) VALUES (?, ?, ...)''',
                   (data['name'], data['crop_type'], ...))
        db.commit()
        return db.execute('SELECT last_insert_rowid()').fetchone()[0]
```

**Common Methods:**
- `get_all()` - Fetch all records
- `get_by_id(id)` - Fetch single record
- `create(data)` - INSERT, return ID
- `update(id, data)` - UPDATE record
- `delete(id)` - DELETE record
- `count()` - Count total records
- `search(keyword)` - LIKE query

**Database Access:**
- Use `get_db()` for connection (Flask g context)
- Row factory returns dict-like objects: `row['field_name']`
- Always commit after mutations: `db.commit()`

### 3. RESTful Route Pattern

**Structure:**
```python
bp = Blueprint('crops', __name__, url_prefix='/crops')

@bp.route('/')              # GET /crops/
def list():
    keyword = request.args.get('keyword', '')
    crops = Crop.search(keyword) if keyword else Crop.get_all()
    return render_template('crops/list.html', crops=crops)

@bp.route('/new')           # GET /crops/new
def new():
    return render_template('crops/form.html', crop=None)

@bp.route('/create', methods=['POST'])  # POST /crops/create
def create():
    data = dict(request.form)
    # Handle image upload
    if 'image' in request.files:
        data['image_path'] = save_image(request.files['image'], 'crops')
    Crop.create(data)
    flash('作物を登録しました', 'success')
    return redirect(url_for('crops.list'))

@bp.route('/<int:id>')      # GET /crops/123
def detail(id):
    crop = Crop.get_by_id(id)
    return render_template('crops/detail.html', crop=crop)

@bp.route('/<int:id>/edit') # GET /crops/123/edit
def edit(id):
    crop = Crop.get_by_id(id)
    return render_template('crops/form.html', crop=crop)

@bp.route('/<int:id>/update', methods=['POST'])  # POST /crops/123/update
def update(id):
    crop = Crop.get_by_id(id)
    data = dict(request.form)

    # Handle image updates
    if 'image' in request.files and request.files['image'].filename:
        if crop['image_path']:
            delete_image(crop['image_path'])
        data['image_path'] = save_image(request.files['image'], 'crops')
    elif 'delete_image' in request.form and crop['image_path']:
        delete_image(crop['image_path'])
        data['image_path'] = None

    Crop.update(id, data)
    flash('作物を更新しました', 'success')
    return redirect(url_for('crops.detail', id=id))

@bp.route('/<int:id>/delete', methods=['POST'])  # POST /crops/123/delete
def delete(id):
    crop = Crop.get_by_id(id)
    if crop['image_path']:
        delete_image(crop['image_path'])
    Crop.delete(id)
    flash('作物を削除しました', 'success')
    return redirect(url_for('crops.list'))
```

**URL Conventions:**
- Plural resource names: `/crops`, `/locations`, `/diary`
- Nested actions: `/<id>/edit`, `/<id>/update`, `/<id>/delete`
- Nested resources: `/locations/<id>/crops/<crop_id>/position`

### 4. Template Inheritance Pattern

**Base Template:** `app/templates/base.html`
- Bootstrap 5.3.0 + Bootstrap Icons
- Navbar with navigation links
- Flash message display system
- Block structure: `title`, `content`, `extra_css`, `extra_js`

**Child Templates:**
```html
{% extends "base.html" %}

{% block title %}作物一覧{% endblock %}

{% block content %}
<div class="container mt-4">
    <h1>作物一覧</h1>
    <!-- Content here -->
</div>
{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/custom.css') }}">
{% endblock %}
```

**Form Pattern (Reusable Create/Edit):**
```html
{% if crop %}
    <form action="{{ url_for('crops.update', id=crop.id) }}" method="post">
{% else %}
    <form action="{{ url_for('crops.create') }}" method="post">
{% endif %}
    <input name="name" value="{{ crop.name if crop else '' }}" required>
    <button type="submit">{{ '更新' if crop else '登録' }}</button>
</form>
```

---

## Database Schema Reference

### Core Tables

**crops** - Crop type definitions
```sql
id INTEGER PRIMARY KEY
name TEXT NOT NULL              -- 作物名 (e.g., "トマト")
crop_type TEXT                  -- 種類 (e.g., "野菜", "果物")
variety TEXT                    -- 品種 (e.g., "ミニトマト")
characteristics TEXT            -- 特徴
planting_season TEXT            -- 植え付け時期
harvest_season TEXT             -- 収穫時期
notes TEXT                      -- メモ
image_path TEXT                 -- 画像パス (migration 003)
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**locations** - Garden locations
```sql
id INTEGER PRIMARY KEY
name TEXT NOT NULL              -- 場所名 (e.g., "南側の畑")
location_type TEXT              -- 種類 (e.g., "畑", "プランター")
area_size REAL                  -- 面積 (㎡)
sun_exposure TEXT               -- 日当たり
notes TEXT
image_path TEXT                 -- 画像パス (migration 003)
canvas_data TEXT                -- キャンバスJSON (migration 001)
created_at TIMESTAMP
updated_at TIMESTAMP
```

**location_crops** - Planting records (many-to-many)
```sql
id INTEGER PRIMARY KEY
location_id INTEGER FK          -- 場所
crop_id INTEGER FK              -- 作物
planted_date DATE               -- 植え付け日
quantity INTEGER                -- 数量
status TEXT CHECK IN ('active', 'harvested', 'removed')  -- 状態
notes TEXT
position_x DECIMAL              -- キャンバス位置X (migration 001)
position_y DECIMAL              -- キャンバス位置Y (migration 001)
created_at TIMESTAMP
updated_at TIMESTAMP
```

**diary_entries** - Cultivation diary (migration 002)
```sql
id INTEGER PRIMARY KEY
title TEXT NOT NULL
content TEXT
entry_date DATE NOT NULL
weather TEXT                    -- 天気
status TEXT DEFAULT 'published'
image_path TEXT                 -- 画像パス (migration 003)
created_at TIMESTAMP
updated_at TIMESTAMP
```

**diary_relations** - Many-to-many diary relations (migration 002)
```sql
id INTEGER PRIMARY KEY
diary_id INTEGER FK             -- 日記エントリ
relation_type TEXT CHECK IN ('crop', 'location', 'location_crop')
crop_id INTEGER FK              -- Optional: 関連する作物
location_id INTEGER FK          -- Optional: 関連する場所
location_crop_id INTEGER FK     -- Optional: 関連する栽培記録
created_at TIMESTAMP
```

### Indexes (Performance Optimization)
```sql
-- Location crops
CREATE INDEX idx_location_crops_location ON location_crops(location_id);
CREATE INDEX idx_location_crops_crop ON location_crops(crop_id);
CREATE INDEX idx_location_crops_status ON location_crops(status);

-- Diary
CREATE INDEX idx_diary_relations_diary ON diary_relations(diary_id);
CREATE INDEX idx_diary_entries_date ON diary_entries(entry_date);
CREATE INDEX idx_diary_relations_crop ON diary_relations(crop_id);
CREATE INDEX idx_diary_relations_location ON diary_relations(location_id);
```

---

## Development Workflows

### Adding a New Feature

**1. Database Changes (if needed)**

Create migration file: `app/migrations/004_feature_name.sql`

```sql
-- Always use IF NOT EXISTS for idempotency
ALTER TABLE crops ADD COLUMN new_field TEXT IF NOT EXISTS;

CREATE TABLE IF NOT EXISTS new_table (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_new_table_name ON new_table(name);
```

**Migration Auto-Execution:**
- Migrations run alphabetically on app startup
- Errors logged but don't crash app (skip "already exists")
- No manual execution needed

**2. Model Updates**

Add methods to existing model or create new model:

```python
# app/models/crop.py
class Crop:
    @staticmethod
    def get_by_season(season):
        db = get_db()
        rows = db.execute(
            'SELECT * FROM crops WHERE planting_season LIKE ? ORDER BY name',
            (f'%{season}%',)
        ).fetchall()
        return [dict(row) for row in rows]
```

**3. Route Implementation**

Add routes to appropriate blueprint:

```python
# app/routes/crop_routes.py
@bp.route('/season/<season>')
def by_season(season):
    crops = Crop.get_by_season(season)
    return render_template('crops/list.html', crops=crops, title=f'{season}の作物')
```

**4. Template Updates**

Create or modify templates:

```html
<!-- app/templates/crops/list.html -->
{% extends "base.html" %}
{% block content %}
<div class="container mt-4">
    <h1>{{ title if title else '作物一覧' }}</h1>
    {% for crop in crops %}
        <div class="card">
            <h5>{{ crop.name }}</h5>
        </div>
    {% endfor %}
</div>
{% endblock %}
```

**5. Testing**

```bash
# Restart app (migrations auto-run)
uv run python run.py

# Test in browser
# Add test data if needed
uv run python test_data.py
```

### Image Upload Workflow

**Integration Pattern:**

```python
from app.utils.upload import save_image, delete_image, allowed_file

# In route create/update
data = dict(request.form)

# Handle new upload
if 'image' in request.files and request.files['image'].filename:
    file = request.files['image']
    if allowed_file(file.filename):
        image_path = save_image(file, 'crops')  # Returns: 'crops/uuid.jpg'
        data['image_path'] = image_path
    else:
        flash('許可されていないファイル形式です', 'error')
        return redirect(...)

# Handle deletion (on update)
if 'delete_image' in request.form and entity['image_path']:
    delete_image(entity['image_path'])
    data['image_path'] = None

# Handle deletion (on entity delete)
if entity['image_path']:
    delete_image(entity['image_path'])
```

**Template Pattern:**

```html
<!-- Upload form -->
<form method="post" enctype="multipart/form-data">
    <input type="file" name="image" accept="image/png,image/jpeg,image/gif,image/webp">
    {% if entity and entity.image_path %}
        <label>
            <input type="checkbox" name="delete_image"> 画像を削除
        </label>
    {% endif %}
</form>

<!-- Display image -->
{% if entity.image_path %}
<img src="{{ url_for('static', filename='uploads/' + entity.image_path) }}"
     class="img-fluid" alt="{{ entity.name }}">
{% endif %}
```

**Key Files:**
- `app/utils/upload.py` - Helper functions
- `app/static/uploads/{crops,locations,diary}/` - Storage folders
- Config: `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH`, `ALLOWED_EXTENSIONS`

### Canvas Editor Integration

**Canvas Data Flow:**
1. User edits canvas in `locations/canvas.html`
2. Auto-save (3s debounce) → POST `/locations/<id>/canvas/save`
3. `Location.save_canvas_data()` stores JSON + updates location_crop positions
4. Position updates via drag → POST `/locations/<id>/crops/<lc_id>/position`

**Canvas JSON Structure:**
```json
{
  "version": "1.0",
  "objects": [
    {
      "type": "group",
      "left": 120,
      "top": 80,
      "cropId": 1,
      "locationCropId": 5,
      "cropName": "ミニトマト",
      "plantedDate": "2024-05-15"
    },
    {
      "type": "rect",
      "left": 50,
      "top": 50,
      "width": 200,
      "height": 150,
      "fill": "rgba(76, 175, 80, 0.3)"
    }
  ]
}
```

**Adding Canvas Features:**

```javascript
// app/static/js/canvas-editor.js

class CanvasEditor {
    addCustomTool() {
        // 1. Add tool button to toolbar
        const toolBtn = document.createElement('button');
        toolBtn.id = 'customTool';
        toolBtn.innerHTML = '<i class="bi-icon"></i>';
        document.querySelector('.tool-palette').appendChild(toolBtn);

        // 2. Register keyboard shortcut
        this.addKeyboardShortcut('X', 'customTool');

        // 3. Implement tool logic
        this.canvas.on('mouse:down', (e) => {
            if (this.activeTool !== 'customTool') return;
            // Tool implementation
        });
    }
}
```

**Crop Sidebar Pattern:**
```html
<!-- canvas.html -->
<div class="crop-sidebar">
    {% for lc in location_crops %}
    <div class="crop-item" draggable="true"
         data-crop-id="{{ lc.crop_id }}"
         data-location-crop-id="{{ lc.id }}"
         data-crop-name="{{ lc.crop_name }}"
         data-planted-date="{{ lc.planted_date }}">
        {{ lc.crop_name }}
    </div>
    {% endfor %}
</div>
```

---

## Code Conventions

### Python Style
- **Naming:**
  - Classes: `PascalCase` (Crop, Location, DiaryEntry)
  - Functions/variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
- **Imports:** Group by stdlib → third-party → local
- **Docstrings:** Not required (code is self-documenting)
- **Type hints:** Not used (Flask context)

### SQL Conventions
- **Tables:** Lowercase plural (crops, locations, diary_entries)
- **Columns:** Lowercase snake_case (crop_type, planted_date, image_path)
- **Foreign keys:** Singular entity name + `_id` (crop_id, location_id)
- **Timestamps:** Always include `created_at`, `updated_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- **Status fields:** Text enums ('active', 'harvested', 'removed')

### Template Conventions
- **Files:** Lowercase, organized by entity (crops/list.html, locations/detail.html)
- **Shared forms:** `form.html` reused for create/edit with conditional logic
- **CSS classes:** Bootstrap utilities + custom kebab-case (.crop-sidebar, .canvas-editor)
- **Flash categories:** 'success', 'error', 'warning', 'info' (Bootstrap alert classes)

### JavaScript Conventions
- **Naming:** camelCase (variables, functions), PascalCase (classes)
- **Organization:** Classes for complex features (CanvasEditor), utility functions for simple tasks
- **Event delegation:** Prefer delegated listeners for dynamic content
- **AJAX:** Use native fetch() for API calls

### URL Routing Conventions
- **Resources:** Plural names (`/crops`, `/locations`, `/diary`)
- **Actions:** Verb-based suffixes (`/create`, `/update`, `/delete`, `/plant`, `/harvest`)
- **IDs:** Integer parameters (`/<int:id>`, `/<int:crop_id>`)
- **Nesting:** Logical hierarchy (`/locations/<id>/crops/<crop_id>/position`)

---

## Common Tasks

### Adding a New Entity Type

**1. Database Schema** (`app/schema.sql` or migration)
```sql
CREATE TABLE IF NOT EXISTS new_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    image_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_new_entities_name ON new_entities(name);
```

**2. Model** (`app/models/new_entity.py`)
```python
from app.database import get_db

class NewEntity:
    @staticmethod
    def get_all():
        db = get_db()
        return [dict(row) for row in db.execute('SELECT * FROM new_entities').fetchall()]

    @staticmethod
    def get_by_id(entity_id):
        db = get_db()
        row = db.execute('SELECT * FROM new_entities WHERE id = ?', (entity_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(data):
        db = get_db()
        db.execute(
            'INSERT INTO new_entities (name, description, image_path) VALUES (?, ?, ?)',
            (data.get('name'), data.get('description'), data.get('image_path'))
        )
        db.commit()
        return db.execute('SELECT last_insert_rowid()').fetchone()[0]

    @staticmethod
    def update(entity_id, data):
        db = get_db()
        db.execute(
            'UPDATE new_entities SET name = ?, description = ?, image_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (data.get('name'), data.get('description'), data.get('image_path'), entity_id)
        )
        db.commit()

    @staticmethod
    def delete(entity_id):
        db = get_db()
        db.execute('DELETE FROM new_entities WHERE id = ?', (entity_id,))
        db.commit()
```

**3. Routes** (`app/routes/new_entity_routes.py`)
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.new_entity import NewEntity
from app.utils.upload import save_image, delete_image

bp = Blueprint('new_entities', __name__, url_prefix='/new-entities')

@bp.route('/')
def list():
    entities = NewEntity.get_all()
    return render_template('new_entities/list.html', entities=entities)

@bp.route('/new')
def new():
    return render_template('new_entities/form.html', entity=None)

@bp.route('/create', methods=['POST'])
def create():
    data = dict(request.form)
    if 'image' in request.files and request.files['image'].filename:
        data['image_path'] = save_image(request.files['image'], 'new_entities')
    NewEntity.create(data)
    flash('登録しました', 'success')
    return redirect(url_for('new_entities.list'))

@bp.route('/<int:id>')
def detail(id):
    entity = NewEntity.get_by_id(id)
    return render_template('new_entities/detail.html', entity=entity)

@bp.route('/<int:id>/edit')
def edit(id):
    entity = NewEntity.get_by_id(id)
    return render_template('new_entities/form.html', entity=entity)

@bp.route('/<int:id>/update', methods=['POST'])
def update(id):
    entity = NewEntity.get_by_id(id)
    data = dict(request.form)

    if 'image' in request.files and request.files['image'].filename:
        if entity['image_path']:
            delete_image(entity['image_path'])
        data['image_path'] = save_image(request.files['image'], 'new_entities')
    elif 'delete_image' in request.form and entity['image_path']:
        delete_image(entity['image_path'])
        data['image_path'] = None

    NewEntity.update(id, data)
    flash('更新しました', 'success')
    return redirect(url_for('new_entities.detail', id=id))

@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    entity = NewEntity.get_by_id(id)
    if entity['image_path']:
        delete_image(entity['image_path'])
    NewEntity.delete(id)
    flash('削除しました', 'success')
    return redirect(url_for('new_entities.list'))
```

**4. Register Blueprint** (`app/__init__.py`)
```python
from app.routes import new_entity_routes
app.register_blueprint(new_entity_routes.bp)
```

**5. Create Templates** (`app/templates/new_entities/`)
- `list.html` - Entity listing
- `detail.html` - Single entity view
- `form.html` - Create/edit form

**6. Create Upload Directory**
```bash
mkdir -p app/static/uploads/new_entities
touch app/static/uploads/new_entities/.gitkeep
```

### Adding Search/Filter Functionality

```python
# Model method
@staticmethod
def search(keyword=None, date_from=None, date_to=None):
    db = get_db()
    query = 'SELECT * FROM table_name WHERE 1=1'
    params = []

    if keyword:
        query += ' AND (field1 LIKE ? OR field2 LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%'])

    if date_from:
        query += ' AND date_field >= ?'
        params.append(date_from)

    if date_to:
        query += ' AND date_field <= ?'
        params.append(date_to)

    query += ' ORDER BY created_at DESC'
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]

# Route usage
@bp.route('/')
def list():
    keyword = request.args.get('keyword', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    entities = Model.search(keyword, date_from, date_to)
    return render_template('list.html', entities=entities,
                          keyword=keyword, date_from=date_from, date_to=date_to)
```

### Adding Many-to-Many Relationships

**Example: Linking diary entries to crops/locations**

```python
# Model methods (DiaryEntry)
@staticmethod
def get_relations(diary_id):
    db = get_db()
    rows = db.execute('''
        SELECT dr.*, c.name as crop_name, l.name as location_name
        FROM diary_relations dr
        LEFT JOIN crops c ON dr.crop_id = c.id
        LEFT JOIN locations l ON dr.location_id = l.id
        WHERE dr.diary_id = ?
    ''', (diary_id,)).fetchall()
    return [dict(row) for row in rows]

@staticmethod
def save_relations(diary_id, relations):
    db = get_db()
    # Clear existing relations
    db.execute('DELETE FROM diary_relations WHERE diary_id = ?', (diary_id,))

    # Insert new relations
    for rel in relations:
        db.execute('''
            INSERT INTO diary_relations (diary_id, relation_type, crop_id, location_id, location_crop_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (diary_id, rel['type'], rel.get('crop_id'), rel.get('location_id'), rel.get('location_crop_id')))

    db.commit()

# Route usage
@bp.route('/create', methods=['POST'])
def create():
    data = dict(request.form)
    diary_id = DiaryEntry.create(data)

    # Handle relations
    relations = []
    if 'crop_ids' in request.form:
        for crop_id in request.form.getlist('crop_ids'):
            relations.append({'type': 'crop', 'crop_id': crop_id})

    DiaryEntry.save_relations(diary_id, relations)
    return redirect(url_for('diary.detail', id=diary_id))
```

---

## Troubleshooting

### Database Issues

**Database not initializing:**
```bash
# Manual initialization
uv run python -c "from app import create_app; from app.database import init_db; app = create_app(); init_db(app)"
```

**Migration errors:**
- Check SQL syntax in migration files
- Ensure migrations use `IF NOT EXISTS` for idempotency
- Check migration numbering sequence (001, 002, 003...)
- Look at logs in console during app startup

**Locked database:**
```bash
# SQLite locks when multiple processes access it
# Kill other Python processes or restart
pkill -f "python run.py"
```

### Image Upload Issues

**Images not saving:**
- Check directory exists: `app/static/uploads/{folder}/`
- Check file permissions
- Verify `MAX_CONTENT_LENGTH` config (16MB default)
- Check allowed extensions in `upload.py`

**Images not displaying:**
- Verify path format: `folder/filename.ext` (no leading slash)
- Check template uses: `url_for('static', filename='uploads/' + path)`
- Verify file exists in filesystem

### Canvas Issues

**Canvas not saving:**
- Check browser console for JavaScript errors
- Verify endpoint: POST `/locations/<id>/canvas/save`
- Check JSON format validity
- Ensure location_id exists in database

**Crop positions not updating:**
- Verify `position_x` and `position_y` columns exist (migration 001)
- Check endpoint: POST `/locations/<id>/crops/<lc_id>/position`
- Verify location_crop_id is valid

---

## Best Practices for AI Assistants

### When Making Changes

1. **Read before modifying:** Always use Read tool to examine existing files before making changes
2. **Follow existing patterns:** Match the style and structure of existing code
3. **Maintain conventions:** Use established naming patterns and file organization
4. **Test after changes:** Verify changes work before considering task complete
5. **Keep it simple:** Don't over-engineer; match the current complexity level

### Database Changes

1. **Always create migrations:** Never modify `schema.sql` directly for new features
2. **Use IF NOT EXISTS:** Make migrations idempotent
3. **Number sequentially:** Use 3-digit prefixes (001, 002, 003...)
4. **Add indexes:** For foreign keys and commonly queried fields
5. **Update model methods:** Add corresponding Python methods for new fields/tables

### Code Organization

1. **One feature per file:** Keep routes/models focused on single entity
2. **Reuse templates:** Use conditional logic in forms instead of separate files
3. **Centralize utilities:** Put shared code in `app/utils/`
4. **Follow blueprint pattern:** Register all routes via blueprints
5. **Avoid duplication:** Extract common patterns into helper functions

### UI/UX Considerations

1. **Bootstrap first:** Use Bootstrap utilities before writing custom CSS
2. **Flash messages:** Always provide user feedback for actions
3. **Confirmation dialogs:** Use `confirmDelete()` from main.js for deletions
4. **Responsive design:** Test on multiple screen sizes
5. **Accessibility:** Include alt text for images, labels for inputs

### Security Considerations

1. **Validate file uploads:** Check extensions via `allowed_file()`
2. **Sanitize input:** Use parameterized queries (already done with `?` placeholders)
3. **Check permissions:** Verify entity exists before deletion/updates
4. **Handle errors gracefully:** Use try/except for file operations
5. **Don't expose internals:** Return appropriate error messages to users

---

## Appendix: Full Model API Reference

### Crop Model (`app/models/crop.py`)

```python
Crop.get_all() → List[Dict]
Crop.get_by_id(crop_id: int) → Dict | None
Crop.create(data: Dict) → int  # Returns inserted ID
Crop.update(crop_id: int, data: Dict) → None
Crop.delete(crop_id: int) → None
Crop.count() → int
Crop.search(keyword: str) → List[Dict]
```

### Location Model (`app/models/location.py`)

```python
Location.get_all() → List[Dict]
Location.get_by_id(location_id: int) → Dict | None
Location.create(data: Dict) → int
Location.update(location_id: int, data: Dict) → None
Location.delete(location_id: int) → None
Location.count() → int
Location.search(keyword: str) → List[Dict]
Location.get_canvas_data(location_id: int) → str | None  # JSON string
Location.save_canvas_data(location_id: int, canvas_dict: Dict) → None
```

### LocationCrop Model (`app/models/location_crop.py`)

```python
LocationCrop.get_by_location(location_id: int, status: str = 'active') → List[Dict]
LocationCrop.get_by_crop(crop_id: int, status: str = 'active') → List[Dict]
LocationCrop.get_by_id(location_crop_id: int) → Dict | None
LocationCrop.plant(data: Dict) → int  # Creates planting record
LocationCrop.harvest(location_crop_id: int) → None  # Sets status='harvested'
LocationCrop.remove(location_crop_id: int) → None  # Sets status='removed'
LocationCrop.count_active() → int
LocationCrop.get_all_active() → List[Dict]  # All active plantings with details
LocationCrop.update_position(location_crop_id: int, x: float, y: float) → None
LocationCrop.get_crops_with_position(location_id: int) → List[Dict]
LocationCrop.clear_positions_except(location_id: int, location_crop_ids: List[int]) → None
```

### DiaryEntry Model (`app/models/diary.py`)

```python
DiaryEntry.get_all(limit: int = None, offset: int = 0) → List[Dict]
DiaryEntry.get_by_id(diary_id: int) → Dict | None
DiaryEntry.create(data: Dict) → int
DiaryEntry.update(diary_id: int, data: Dict) → None
DiaryEntry.delete(diary_id: int) → None
DiaryEntry.count() → int
DiaryEntry.search(keyword: str = None, date_from: str = None, date_to: str = None) → List[Dict]
DiaryEntry.get_recent(limit: int = 5) → List[Dict]
DiaryEntry.get_relations(diary_id: int) → List[Dict]
DiaryEntry.save_relations(diary_id: int, relations: List[Dict]) → None
DiaryEntry.get_by_crop(crop_id: int) → List[Dict]
DiaryEntry.get_by_location(location_id: int) → List[Dict]
```

---

## Additional Resources

### Configuration Reference (`app/config.py`)

```python
class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    DATABASE = os.path.join(Config.BASE_DIR, 'instance', 'garden.db')
    SECRET_KEY = 'dev-secret-key-change-in-production'
    UPLOAD_FOLDER = os.path.join(Config.BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
```

### Canvas Editor Keyboard Shortcuts

- `S` - Select tool
- `R` - Rectangle tool
- `C` - Circle tool
- `L` - Line tool
- `T` - Text tool
- `D` - Delete selected objects
- `Ctrl+Z` / `Cmd+Z` - Undo
- `Ctrl+Shift+Z` / `Cmd+Shift+Z` - Redo
- `Delete` / `Backspace` - Delete selected

### Fabric.js Integration Points

**Key Methods in CanvasEditor:**
```javascript
constructor(canvasElementId, locationId)  // Initialize canvas
loadCanvas()                              // Load canvas data from server
saveCanvas()                              // Debounced auto-save (3 seconds)
addCropToCanvas(cropData)                 // Add crop icon to canvas
updateCropPosition(locationCropId, x, y)  // Sync position to server
addToHistory()                            // Save state for undo/redo
undo() / redo()                           // History navigation
enableDrawingMode(tool)                   // Activate drawing tool
```

---

## Quick Decision Tree

**Need to add a field to existing entity?**
→ Create migration, update model method, update form template

**Need to add a new page?**
→ Add route function, create template extending base.html

**Need to track relationships between entities?**
→ Create junction table (like diary_relations), add model methods for get/save

**Need to add image upload?**
→ Use `save_image()` in route, add `enctype="multipart/form-data"` to form

**Need to add search?**
→ Add search method to model with LIKE queries, add search form to list template

**Canvas feature request?**
→ Modify canvas-editor.js, test in locations/canvas.html

**Need API endpoint?**
→ Add JSON response route, test with fetch() from JavaScript

This document should be updated as the codebase evolves to reflect new patterns and conventions.
