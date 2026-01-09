from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignUpForm, LoginForm, PostForm, CommentForm, StoryForm, ProfileForm
from .models import (
    Post, Profile, Notification, MessageThread, Message,
    Like, Comment, Follow, Story
)
from .models import StoryView

from django.contrib import messages as dj_messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync



def push_notification(user, text, title='Activity'):
    n = Notification.objects.create(user=user, text=text)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notif_{user.id}',
        {
            'type': 'notif.message',
            'title': title,
            'text': text,
            'created_at': n.created_at.isoformat(),
        }
    )


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
        )
        login(request, user)
        dj_messages.success(request, 'Welcome! Account created.')
        return redirect('home')
    return render(request, 'core/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        dj_messages.success(request, 'Logged in successfully.')
        return redirect('home')
    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    logout(request)
    dj_messages.info(request, 'Logged out.')
    return redirect('login')


@login_required
def home_view(request):
    posts = (
        Post.objects.select_related('author')
        .prefetch_related('comments__author', 'likes__user')
        .order_by('-created_at')
    )
    # Active stories in last 24h
    recent_stories = Story.objects.filter(created_at__gte=timezone.now() - timedelta(hours=24)).select_related('user').order_by('-created_at')
    # Build per-user story summary with viewed/unviewed status
    story_by_user = {}
    for s in recent_stories:
        if s.user_id not in story_by_user:
            story_by_user[s.user_id] = {'user': s.user, 'story': s}
    story_users = []
    for info in story_by_user.values():
        u = info['user']
        s = info['story']
        Profile.objects.get_or_create(user=u)
        # Determine if there exists at least one story for that user the current viewer hasn't seen
        user_stories = recent_stories.filter(user=u)
        has_unviewed = False
        for us in user_stories:
            if not StoryView.objects.filter(story=us, viewer=request.user).exists():
                has_unviewed = True
                break
        story_users.append({'user': u, 'story': s, 'unviewed': has_unviewed})
    # Precompute which users the current user is following for template checks
    following_ids = list(Follow.objects.filter(follower=request.user).values_list('following_id', flat=True))

    return render(request, 'core/home.html', {
        'posts': posts,
        'comment_form': CommentForm(),
        'stories': story_users,
        'following_ids': following_ids,
    })


@login_required
def search_view(request):
    q = request.GET.get('q', '').strip()
    users = None  # initial state: do not show "No users found"
    if q:
        users = User.objects.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        ).select_related('profile')[:50]
    return render(request, 'core/search.html', {'q': q, 'users': users})


@login_required
def explore_view(request):
    posts = Post.objects.select_related('author').order_by('-created_at')
    return render(request, 'core/explore.html', {'posts': posts})


@login_required
def reels_view(request):
    # Only videos, newest first
    videos = [p for p in Post.objects.order_by('-created_at') if p.is_video]
    return render(request, 'core/reels.html', {'videos': videos})


@login_required
def messages_view(request):
    q = request.GET.get('q', '').strip()
    threads = MessageThread.objects.filter(participants=request.user).prefetch_related('participants').order_by('-created_at')
    results = None
    if q:
        results = User.objects.filter(username__icontains=q).exclude(id=request.user.id).select_related('profile')[:50]
    # When searching, hide previous chats and show results only (handled in template)
    thread_id = request.GET.get('t')
    selected_thread = None
    msgs = []
    if not q:  # only resolve threads/messages when not searching
        if thread_id:
            selected_thread = get_object_or_404(MessageThread, id=thread_id)
            if not selected_thread.participants.filter(id=request.user.id).exists():
                return HttpResponseForbidden("Not allowed")
            msgs = selected_thread.messages.select_related('sender').order_by('created_at')
        elif threads.exists():
            selected_thread = threads.first()
            msgs = selected_thread.messages.select_related('sender').order_by('created_at')

    # compute chat partner for header display
    chat_partner = None
    if selected_thread:
        other = selected_thread.participants.exclude(id=request.user.id).first()
        chat_partner = other

    return render(request, 'core/messages.html', {
        'threads': threads,
        'selected_thread': selected_thread,
        'chat_messages': msgs,
        'q': q,
        'results': results,
        'chat_partner': chat_partner,
    })


@login_required
def mark_story_viewed(request):
    """AJAX endpoint to mark a story viewed by the current user.

    Expects POST with 'story_id'. Returns JSON {ok: true}.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    story_id = request.POST.get('story_id') or request.POST.get('id')
    if not story_id:
        return JsonResponse({'error': 'missing story_id'}, status=400)
    try:
        s = Story.objects.get(id=int(story_id))
    except (Story.DoesNotExist, ValueError):
        return JsonResponse({'error': 'invalid story'}, status=404)
    # create view record if not exists
    StoryView.objects.get_or_create(story=s, viewer=request.user)
    return JsonResponse({'ok': True})


@login_required
def message_upload_view(request):
    """Handle file uploads for a thread. Creates Message with attachment and broadcasts it."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    thread_id = request.POST.get('thread_id')
    text = request.POST.get('text', '').strip()
    file = request.FILES.get('file')
    if not thread_id:
        return JsonResponse({'error': 'missing thread_id'}, status=400)
    try:
        thread = MessageThread.objects.get(id=int(thread_id))
    except (MessageThread.DoesNotExist, ValueError):
        return JsonResponse({'error': 'invalid thread'}, status=404)
    if not thread.participants.filter(id=request.user.id).exists():
        return HttpResponseForbidden('Not allowed')

    m = Message.objects.create(thread=thread, sender=request.user, text=text or '', attachment=file if file else None)

    # broadcast to channel layer so WS clients get the new message
    channel_layer = get_channel_layer()
    payload = {
        'type': 'chat.message',
        'message_id': m.id,
        'sender': m.sender.username,
        'text': m.text,
        'created_at': m.created_at.isoformat(),
    }
    if m.attachment:
        payload['attachment_url'] = m.attachment.url
    async_to_sync(channel_layer.group_send)(f'chat_{thread.id}', payload)

    return JsonResponse({
        'id': m.id,
        'sender': m.sender.username,
        'text': m.text,
        'created_at': m.created_at.isoformat(),
        'attachment_url': m.attachment.url if m.attachment else None,
    })


@login_required
def start_thread_view(request, username):
    other = get_object_or_404(User, username=username)
    if other == request.user:
        dj_messages.info(request, "You can't start a thread with yourself.")
        return redirect('messages')
    thread = (
        MessageThread.objects.filter(participants=request.user)
        .filter(participants=other).first()
    )
    if not thread:
        thread = MessageThread.objects.create()
        thread.participants.add(request.user, other)
    return redirect(f"{reverse('messages')}?t={thread.id}")


@login_required
def notifications_view(request):
    raw = request.user.notifications.order_by('-created_at')[:50]
    # Attach actor (if present) via a reliable relation if Notification has actor FK;
    # otherwise attempt to resolve from text prefix, safely.
    notifs = []
    for n in raw:
        actor = None
        try:
            # Try resolving an actor via notification text prefix (safe, non-db call)
            candidate = (n.text or '').split()[0]
            actor = User.objects.filter(username=candidate).first()
        except Exception:
            actor = None
        if actor:
            Profile.objects.get_or_create(user=actor)
        # `post` may not exist in this schema; include None for template safety
        post_obj = getattr(n, 'post', None) if hasattr(n, 'post') else None
        notifs.append({'notif': n, 'actor': actor, 'post': post_obj})
    return render(request, 'core/notifications.html', {'notifs': notifs})


@login_required
def profile_edit_view(request, username):
    if request.user.username != username:
        dj_messages.error(request, 'Not allowed')
        return redirect('profile', username=username)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        dj_messages.success(request, 'Profile updated.')
        return redirect('profile', username=request.user.username)
    return render(request, 'core/profile_edit.html', {'form': form})


@login_required
def post_delete_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.author != request.user:
        dj_messages.error(request, 'Not allowed')
        return redirect('profile', username=request.user.username)
    if request.method == 'POST':
        post.delete()
        dj_messages.success(request, 'Post deleted.')
        return redirect('profile', username=request.user.username)
    return redirect('profile', username=request.user.username)


@login_required
def create_post_view(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        push_notification(request.user, 'You posted new content.', title='Post uploaded')
        dj_messages.success(request, 'Post created.')
        return redirect('home')
    return render(request, 'core/create_post.html', {'form': form})


@login_required
def profile_view(request, username):
    user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=user)
    posts = user.posts.order_by('-created_at')
    photos = [p for p in posts if not p.is_video]
    videos = [p for p in posts if p.is_video]
    stats = {
        'posts': posts.count(),
        'followers': Follow.objects.filter(following=user).count(),
        'following': Follow.objects.filter(follower=user).count(),
    }
    is_following = None if request.user == user else Follow.objects.filter(follower=request.user, following=user).exists()
    return render(request, 'core/profile.html', {
        'profile_user': user,
        'profile': profile,
        'posts': posts,
        'photos': photos,
        'videos': videos,
        'stats': stats,
        'is_following': is_following,
    })


@login_required
def add_story_view(request):
    form = StoryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        story = form.save(commit=False)
        story.user = request.user
        story.save()
        dj_messages.success(request, 'Story added!')
        return redirect('home')
    return render(request, 'core/add_story.html', {'form': form})


# AJAX endpoints
@login_required
def like_toggle_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        if request.user != post.author:
            push_notification(post.author, f'{request.user.username} liked your post.', title='New like')
    return JsonResponse({'liked': liked, 'count': post.likes.count()})


@login_required
def comment_create_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    text = request.POST.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Empty comment'}, status=400)
    c = Comment.objects.create(post=post, author=request.user, text=text)
    if request.user != post.author:
        push_notification(post.author, f'{request.user.username} commented: "{text}"', title='New comment')
    return JsonResponse({
        'id': c.id,
        'author': c.author.username,
        'text': c.text,
        'created_at': c.created_at.isoformat(),
        'count': post.comments.count(),
    })


@login_required
def follow_toggle_view(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({'error': "Can't follow yourself"}, status=400)
    rel, created = Follow.objects.get_or_create(follower=request.user, following=target)
    if not created:
        rel.delete()
        following = False
    else:
        following = True
        push_notification(target, f'{request.user.username} started following you.', title='New follower')
    followers_count = Follow.objects.filter(following=target).count()
    return JsonResponse({'following': following, 'followers': followers_count})