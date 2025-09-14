#!/usr/bin/env python
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib.auth import get_user_model

User = get_user_model()

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        This method is called after a successful authentication from the provider
        but before the login is actually processed.
        We use it to connect the social account to an existing user by email.
        """
        if sociallogin.is_existing:
            return  # already linked

        # Try to find existing user with same email
        email = sociallogin.user.email
        if not email:
            return

        try:
            user = User.objects.get(email__iexact=email)
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            # no local user with that email
            raise ImmediateHttpResponse(redirect('att:unauthorised'))
