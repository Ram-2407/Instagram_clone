from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import Profile, Post, Comment, Like, Follow, Story, MessageThread, Message

class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')

    def test_profile_creation(self):
        # Profile created by signal
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(str(profile), 'testuser')
        self.assertEqual(profile.avatar_url, '/static/core/default-avatar.svg')

    def test_post_creation(self):
        post = Post.objects.create(
            author=self.user,
            caption='Test Caption',
            media=SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")
        )
        self.assertEqual(str(post), f'testuser:{post.id}')
        self.assertFalse(post.is_video)
        
        video_post = Post.objects.create(
            author=self.user,
            caption='Video Caption',
            media=SimpleUploadedFile("test_video.mp4", b"file_content", content_type="video/mp4")
        )
        self.assertTrue(video_post.is_video)

    def test_comment_creation(self):
        post = Post.objects.create(
            author=self.user,
            media=SimpleUploadedFile("test.jpg", b"content")
        )
        comment = Comment.objects.create(post=post, author=self.other_user, text='Nice!')
        self.assertEqual(str(comment), f'Comment by otheruser on {post.id}')

    def test_like_creation(self):
        post = Post.objects.create(
            author=self.user,
            media=SimpleUploadedFile("test.jpg", b"content")
        )
        like = Like.objects.create(post=post, user=self.other_user)
        self.assertEqual(str(like), f'otheruser liked {post.id}')

    def test_follow_creation(self):
        follow = Follow.objects.create(follower=self.user, following=self.other_user)
        self.assertEqual(str(follow), 'testuser → otheruser')

    def test_story_logic(self):
        story = Story.objects.create(
            user=self.user,
            media=SimpleUploadedFile("story.jpg", b"content")
        )
        self.assertTrue(story.is_active())
        self.assertFalse(story.is_video)
        
        # Simulate old story
        story.created_at = timezone.now() - timedelta(hours=25)
        story.save()
        self.assertFalse(story.is_active())

    def test_message_creation(self):
        thread = MessageThread.objects.create()
        thread.participants.add(self.user, self.other_user)
        msg = Message.objects.create(thread=thread, sender=self.user, text='Hello')
        self.assertEqual(str(msg), f'Message {msg.id} by testuser')


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')

    def test_signup_view(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertEqual(response.status_code, 302) # Redirects to home
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_login_view(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'password'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)

    def test_home_view_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/home.html')

    def test_home_view_anonymous(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302) # Redirects to login

    def test_profile_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('profile', args=[self.user.username]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/profile.html')

    def test_create_post_view(self):
        self.client.force_login(self.user)
        image = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")
        
        response = self.client.post(reverse('create_post'), {
            'caption': 'New Post',
            'media': image
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Post.objects.filter(caption='New Post').exists())

    def test_like_toggle_view(self):
        self.client.force_login(self.user)
        post = Post.objects.create(author=self.other_user, media=SimpleUploadedFile("t.jpg", b"c"))
        
        response = self.client.post(reverse('like_toggle', args=[post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Like.objects.filter(user=self.user, post=post).exists())
        
        # Toggle off
        response = self.client.post(reverse('like_toggle', args=[post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Like.objects.filter(user=self.user, post=post).exists())

    def test_comment_create_view(self):
        self.client.force_login(self.user)
        post = Post.objects.create(author=self.other_user, media=SimpleUploadedFile("t.jpg", b"c"))
        
        response = self.client.post(reverse('comment_create', args=[post.id]), {'text': 'Great!'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Comment.objects.filter(author=self.user, post=post, text='Great!').exists())
