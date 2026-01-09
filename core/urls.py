from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Home
    path('', login_required(views.home_view), name='home'),

    # Core features
    path('search/', login_required(views.search_view), name='search'),
    path('explore/', login_required(views.explore_view), name='explore'),
    path('reels/', login_required(views.reels_view), name='reels'),

    path('messages/', login_required(views.messages_view), name='messages'),
    path('messages/start/<str:username>/', login_required(views.start_thread_view), name='start_thread'),

    path('notifications/', login_required(views.notifications_view), name='notifications'),

    path('create/', login_required(views.create_post_view), name='create_post'),
    path('profile/<str:username>/', login_required(views.profile_view), name='profile'),
    path('profile/<str:username>/edit/', login_required(views.profile_edit_view), name='profile_edit'),

    path('post/delete/<int:post_id>/', login_required(views.post_delete_view), name='post_delete'),

    # Stories
    path('stories/add/', login_required(views.add_story_view), name='add_story'),
    path('stories/mark_viewed/', login_required(views.mark_story_viewed), name='mark_story_viewed'),
    path('messages/upload/', login_required(views.message_upload_view), name='message_upload'),

    # AJAX endpoints (protected)
    path('api/like/<int:post_id>/', login_required(views.like_toggle_view), name='like_toggle'),
    path('api/comment/<int:post_id>/', login_required(views.comment_create_view), name='comment_create'),
    path('api/follow/<str:username>/', login_required(views.follow_toggle_view), name='follow_toggle'),
]