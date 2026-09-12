import json
from app.models import db, Category, MenuItem

POPULAR_TOPPINGS = [
    {'name': 'Pepperoni', 'category': 'Meats', 'price_modifier': 1.50},
    {'name': 'Italian Sausage', 'category': 'Meats', 'price_modifier': 1.50},
    {'name': 'Applewood Smoked Bacon', 'category': 'Meats', 'price_modifier': 1.50},
    {'name': 'Roasted Mushrooms', 'category': 'Veggies', 'price_modifier': 1.00},
    {'name': 'Black Olives', 'category': 'Veggies', 'price_modifier': 1.00},
    {'name': 'Green Bell Peppers', 'category': 'Veggies', 'price_modifier': 1.00},
    {'name': 'Red Onions', 'category': 'Veggies', 'price_modifier': 1.00},
    {'name': 'Pickled Jalapeños', 'category': 'Veggies', 'price_modifier': 1.00},
    {'name': 'Fresh Sweet Basil', 'category': 'Veggies', 'price_modifier': 1.00},
    {'name': 'Extra Whole Milk Mozzarella', 'category': 'Cheese', 'price_modifier': 1.50},
    {'name': 'Wisconsin Brick Cheese', 'category': 'Cheese', 'price_modifier': 1.50},
]

def seed_database():
    """Seed initial categories and menu items if database is empty, or update existing item options."""
    if Category.query.first() is not None:
        # Patch existing menu items if their toppings list differs from current POPULAR_TOPPINGS
        updated = False
        for item in MenuItem.query.all():
            opts = item.get_options()
            if opts and 'sizes' in opts and opts.get('sizes'):
                if opts.get('toppings') != POPULAR_TOPPINGS:
                    opts['toppings'] = POPULAR_TOPPINGS
                    item.options_json = json.dumps(opts)
                    updated = True
        if updated:
            db.session.commit()
        return

    categories_data = [
        {
            'name': 'Specialty Pizzas',
            'slug': 'specialty-pizzas',
            'description': 'Handcrafted artisan pizzas baked in our stone-deck oven.',
            'display_order': 1
        },
        {
            'name': 'Build Your Own',
            'slug': 'build-your-own',
            'description': 'Create your masterpiece with your choice of crust, sauce, and premium toppings.',
            'display_order': 2
        },
        {
            'name': 'Appetizers & Sides',
            'slug': 'appetizers-sides',
            'description': 'Irresistible starters made fresh daily to kick off your feast.',
            'display_order': 3
        },
        {
            'name': 'Beverages',
            'slug': 'beverages',
            'description': 'Refreshing soft drinks, sparkling waters, and handcrafted Italian sodas.',
            'display_order': 4
        },
        {
            'name': 'Desserts',
            'slug': 'desserts',
            'description': 'Classic Italian sweet treats to end your meal on a high note.',
            'display_order': 5
        }
    ]

    cat_map = {}
    for cdata in categories_data:
        cat = Category(
            name=cdata['name'],
            slug=cdata['slug'],
            description=cdata['description'],
            display_order=cdata['display_order']
        )
        db.session.add(cat)
        cat_map[cdata['name']] = cat

    db.session.flush()

    pizza_options = {
        'sizes': [
            {'name': 'Personal (10")', 'price_modifier': 0.0},
            {'name': 'Medium (12")', 'price_modifier': 3.50},
            {'name': 'Large (16")', 'price_modifier': 6.50}
        ],
        'crusts': [
            {'name': 'Classic Hand-Tossed', 'price_modifier': 0.0},
            {'name': 'Crispy Thin Crust', 'price_modifier': 0.0},
            {'name': 'Gluten-Free Cauliflower Crust', 'price_modifier': 2.50},
            {'name': 'Garlic Herb Stuffed Crust', 'price_modifier': 3.00}
        ],
        'toppings': POPULAR_TOPPINGS
    }

    menu_items_data = [
        # Specialty Pizzas
        {
            'category': 'Specialty Pizzas',
            'name': 'Margherita Classico',
            'description': 'San Marzano tomato sauce, fresh buffalo mozzarella, fragrant sweet basil, extra virgin olive oil, and sea salt.',
            'base_price': 14.99,
            'image_url': 'https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': pizza_options
        },
        {
            'category': 'Specialty Pizzas',
            'name': 'Pepperoni Rustica',
            'description': 'Crispy cupping pepperoni slices, whole milk mozzarella, spicy hot honey drizzle, and rich crushed red pepper marinara.',
            'base_price': 16.99,
            'image_url': 'https://images.unsplash.com/photo-1628840042765-356cda07504e?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': pizza_options
        },
        {
            'category': 'Specialty Pizzas',
            'name': 'Truffle Mushroom & Sausage',
            'description': 'Roasted cremini & wild forest mushrooms, sweet Italian fennel sausage, creamy ricotta, white truffle oil, and thyme.',
            'base_price': 18.49,
            'image_url': 'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': pizza_options
        },
        {
            'category': 'Specialty Pizzas',
            'name': 'Smoky BBQ Bacon Chicken',
            'description': 'Grilled chicken breast, applewood smoked bacon, red onions, smoked Gouda, mozzarella, and house honey bourbon BBQ sauce.',
            'base_price': 17.99,
            'image_url': 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': pizza_options
        },
        {
            'category': 'Specialty Pizzas',
            'name': 'Mediterranean Garden Veggie',
            'description': 'Baby spinach, kalamata olives, marinated artichoke hearts, roasted bell peppers, red onions, and crumbled feta cheese.',
            'base_price': 15.99,
            'image_url': 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': pizza_options
        },
        {
            'category': 'Specialty Pizzas',
            'name': 'Diavola Piccante (Seasonal)',
            'description': 'Calabrian chili paste, spicy soppressata, fiery jalapeños, melted provolone, and hot pepper infused olive oil.',
            'base_price': 17.49,
            'image_url': 'https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?auto=format&fit=crop&w=800&q=80',
            'is_available': False,  # Acceptance criteria: unavailable items are hidden or clearly marked
            'options': pizza_options
        },

        # Build Your Own
        {
            'category': 'Build Your Own',
            'name': 'Custom Artisan Pizza',
            'description': 'Start with our slow-fermented dough and signature tomato sauce, then customize size, crust, cheeses, and favorite toppings.',
            'base_price': 12.99,
            'image_url': 'https://images.unsplash.com/photo-1593560708920-61dd98c46a4e?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': pizza_options
        },

        # Appetizers & Sides
        {
            'category': 'Appetizers & Sides',
            'name': 'Garlic Herb Dough Knots',
            'description': 'Six golden oven-baked dough knots brushed with roasted garlic butter, fresh parsley, and grated Parmesan. Served with marinara.',
            'base_price': 6.99,
            'image_url': 'https://images.unsplash.com/photo-1541592106381-b31e9677c0e5?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {
                'sizes': [{'name': '6-Piece Order', 'price_modifier': 0.0}, {'name': '12-Piece Order', 'price_modifier': 4.50}],
                'crusts': []
            }
        },
        {
            'category': 'Appetizers & Sides',
            'name': 'Crispy Mozzarella Bites',
            'description': 'Fresh mozzarella cubes breaded with Italian seasoned crumbs, fried golden and served with warm marinara dipping sauce.',
            'base_price': 7.99,
            'image_url': 'https://images.unsplash.com/photo-1531749668029-2db88e4276c7?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {'sizes': [], 'crusts': []}
        },
        {
            'category': 'Appetizers & Sides',
            'name': 'Classic Caesar Salad',
            'description': 'Crisp romaine lettuce hearts, shaved aged Parmigiano-Reggiano, house-made sourdough croutons, and creamy Caesar dressing.',
            'base_price': 8.99,
            'image_url': 'https://images.unsplash.com/photo-1550304943-4f24f54ddde9?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {
                'sizes': [{'name': 'Side Bowl', 'price_modifier': 0.0}, {'name': 'Entree Size', 'price_modifier': 3.50}],
                'crusts': []
            }
        },

        # Beverages
        {
            'category': 'Beverages',
            'name': 'Italian Sparkling Mineral Water (San Pellegrino)',
            'description': 'Crisp, refreshing imported natural mineral water (500ml bottle).',
            'base_price': 3.49,
            'image_url': 'https://images.unsplash.com/photo-1560512823-829485b8bf24?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {'sizes': [], 'crusts': []}
        },
        {
            'category': 'Beverages',
            'name': 'Blood Orange Italian Aranciata',
            'description': 'Sparkling Italian soda crafted with sun-ripened Sicilian blood oranges.',
            'base_price': 3.99,
            'image_url': 'https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {'sizes': [], 'crusts': []}
        },
        {
            'category': 'Beverages',
            'name': 'Fountain Soda (20 oz)',
            'description': 'Choice of Coca-Cola, Diet Coke, Sprite, Dr Pepper, or Lemonade.',
            'base_price': 2.79,
            'image_url': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {
                'sizes': [
                    {'name': 'Coca-Cola', 'price_modifier': 0.0},
                    {'name': 'Diet Coke', 'price_modifier': 0.0},
                    {'name': 'Sprite', 'price_modifier': 0.0},
                    {'name': 'Dr Pepper', 'price_modifier': 0.0}
                ],
                'crusts': []
            }
        },

        # Desserts
        {
            'category': 'Desserts',
            'name': 'Traditional Mascarpone Tiramisu',
            'description': 'Espresso-soaked Italian ladyfingers layered with velvety mascarpone cream and dusted with Dutch cocoa powder.',
            'base_price': 6.99,
            'image_url': 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {'sizes': [], 'crusts': []}
        },
        {
            'category': 'Desserts',
            'name': 'Sicilian Cannoli Duo',
            'description': 'Two crisp handmade pastry shells filled with sweetened sweet ricotta cream, mini dark chocolate chips, and crushed pistachios.',
            'base_price': 6.49,
            'image_url': 'https://images.unsplash.com/photo-1551529834-525807d6b4f3?auto=format&fit=crop&w=800&q=80',
            'is_available': True,
            'options': {'sizes': [], 'crusts': []}
        }
    ]

    for item in menu_items_data:
        category_obj = cat_map[item['category']]
        menu_item = MenuItem(
            category_id=category_obj.id,
            name=item['name'],
            description=item['description'],
            base_price=item['base_price'],
            image_url=item['image_url'],
            is_available=item['is_available'],
            options_json=json.dumps(item['options'])
        )
        db.session.add(menu_item)

    db.session.commit()
