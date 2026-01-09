from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.CharField(max_length=160, blank=True)

    def __str__(self):
        return self.user.username

    @property
    def avatar_url(self):
        """Return avatar URL or fallback to default static image."""
        return self.avatar.url if self.avatar else '/static/core/default-avatar.svg'


class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    caption = models.TextField(blank=True)
    media = models.FileField(upload_to='posts/')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_video(self):
        return self.media.name.lower().endswith(('.mp4', '.webm', '.mov'))

    def __str__(self):
        return f'{self.author.username}:{self.id}'


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.author.username} on {self.post.id}'


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f'{self.user.username} liked {self.post.id}'


class Follow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following_rel')
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers_rel')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower.username} → {self.following.username}"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField(default=False)


    def __str__(self):
        return f'Notif for {self.user.username}: {self.text}'


class MessageThread(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='threads')
    created_at = models.DateTimeField(auto_now_add=True)
    # updated_at removed to match existing DB schema

    def __str__(self):
        return f'Thread {self.id} with {[u.username for u in self.participants.all()]}'


class Message(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    attachment = models.FileField(upload_to='messages/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Message {self.id} by {self.sender.username}'


class Story(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stories')
    media = models.FileField(upload_to='stories/')
    created_at = models.DateTimeField(auto_now_add=True)

    def is_active(self):
        """Stories expire after 24 hours."""
        return timezone.now() - self.created_at < timedelta(hours=24)

    @property
    def is_video(self):
        return self.media.name.lower().endswith(('.mp4', '.webm', '.mov'))

    def __str__(self):
        return f"{self.user.username}'s story"


class StoryView(models.Model):
    """Record that a particular viewer has seen a specific story."""
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='views')
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='viewed_stories')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('story', 'viewer')

    def __str__(self):
        return f"{self.viewer.username} viewed story {self.story.id}"