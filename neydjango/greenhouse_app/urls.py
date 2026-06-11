
from django.urls import path
from . import views          # DRF API views  → JSON
from . import views_template  # Template views → HTML

app_name = 'greenhouse_app'

urlpatterns = [

    # ── HTML pages (browser) ──────────────────────────────────────────
    path('login/',    views_template.login_view,   name='login'),
    path('logout/',   views_template.logout_view,  name='logout'),

    path('greenhouses/',
         views_template.greenhouse_list,   name='greenhouse_list'),
    path('greenhouses/new/',
         views_template.greenhouse_create, name='greenhouse_create'),
    path('greenhouses/<int:greenhouse_id>/',
         views_template.greenhouse_detail, name='greenhouse_detail'),
    path('greenhouses/<int:greenhouse_id>/edit/',
         views_template.greenhouse_edit,   name='greenhouse_edit'),

    path('greenhouses/<int:greenhouse_id>/houses/new/',
         views_template.house_create, name='house_create'),
    path('greenhouses/<int:greenhouse_id>/houses/<int:house_id>/',
         views_template.house_detail, name='house_detail'),
    path('greenhouses/<int:greenhouse_id>/houses/<int:house_id>/edit/',
         views_template.house_edit,   name='house_edit'),

    path('greenhouses/<int:greenhouse_id>/houses/<int:house_id>/beds/new/',
         views_template.bed_create, name='bed_create'),
    path('greenhouses/<int:greenhouse_id>/houses/<int:house_id>/beds/<int:bed_id>/',
         views_template.bed_detail, name='bed_detail'),
    path('greenhouses/<int:greenhouse_id>/houses/<int:house_id>/beds/<int:bed_id>/edit/',
         views_template.bed_edit,   name='bed_edit'),

    path('greenhouses/<int:greenhouse_id>/houses/<int:house_id>/beds/<int:bed_id>/crops/new/',
         views_template.crop_create, name='crop_create'),
    path('greenhouses/<int:greenhouse_id>/houses/<int:house_id>/beds/<int:bed_id>/crops/<int:crop_id>/edit/',
         views_template.crop_edit,   name='crop_edit'),

    path('greenhouses/<int:greenhouse_id>/members/',
         views_template.member_list,   name='member_list'),
    path('greenhouses/<int:greenhouse_id>/members/add/',
         views_template.member_add,    name='member_add'),
    path('greenhouses/<int:greenhouse_id>/members/<int:member_id>/edit/',
         views_template.member_edit,   name='member_edit'),
    path('greenhouses/<int:greenhouse_id>/members/<int:member_id>/remove/',
         views_template.member_remove, name='member_remove'),

    path('register/', views_template.register_view, name='register'),
    path('profile/', views_template.profile_view, name='profile'),

]