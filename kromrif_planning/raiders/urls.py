from django.urls import path
from . import views

app_name = 'raiders'

urlpatterns = [
    # Character management URLs
    path('characters/', views.CharacterListView.as_view(), name='character-list'),
    path('characters/create/', views.CharacterCreateView.as_view(), name='character-create'),
    path('characters/<int:pk>/', views.CharacterDetailView.as_view(), name='character-detail'),
    path('characters/<int:pk>/edit/', views.CharacterEditView.as_view(), name='character-edit'),
    path('characters/<int:pk>/delete/', views.CharacterDeleteView.as_view(), name='character-delete'),
    
    # HTMX partial views
    path('characters/htmx/list/', views.CharacterListHTMXView.as_view(), name='character-list-htmx'),
    path('characters/htmx/create/', views.CharacterCreateHTMXView.as_view(), name='character-create-htmx'),
    path('characters/htmx/<int:pk>/edit/', views.CharacterEditHTMXView.as_view(), name='character-edit-htmx'),
    path('characters/htmx/<int:pk>/delete/', views.CharacterDeleteHTMXView.as_view(), name='character-delete-htmx'),
    
    # Character search and filtering
    path('characters/search/', views.CharacterSearchView.as_view(), name='character-search'),
    
    # Guild roster URLs
    path('roster/', views.GuildRosterView.as_view(), name='guild-roster'),
    path('roster/htmx/', views.GuildRosterHTMXView.as_view(), name='guild-roster-htmx'),
    path('roster/members/', views.MemberListView.as_view(), name='member-list'),
    path('roster/members/htmx/', views.MemberListHTMXView.as_view(), name='member-list-htmx'),
    
    # Rank management URLs
    path('ranks/', views.RankListView.as_view(), name='rank-list'),
    path('ranks/create/', views.RankCreateView.as_view(), name='rank-create'),
    path('ranks/<int:pk>/', views.RankDetailView.as_view(), name='rank-detail'),
    path('ranks/<int:pk>/edit/', views.RankEditView.as_view(), name='rank-edit'),
    path('ranks/<int:pk>/delete/', views.RankDeleteView.as_view(), name='rank-delete'),
    
    # HTMX rank management
    path('ranks/htmx/create/', views.RankCreateHTMXView.as_view(), name='rank-create-htmx'),
    path('ranks/htmx/<int:pk>/edit/', views.RankEditHTMXView.as_view(), name='rank-edit-htmx'),
    path('ranks/htmx/<int:pk>/delete/', views.RankDeleteHTMXView.as_view(), name='rank-delete-htmx'),
]