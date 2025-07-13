from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.views import View
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import get_user_model
from .models import Character, Rank, CharacterOwnership
from .forms import CharacterForm, CharacterSearchForm, RankForm, MemberSearchForm

User = get_user_model()


class CharacterListView(LoginRequiredMixin, ListView):
    """Main character list view"""
    model = Character
    template_name = 'raiders/character_list.html'
    context_object_name = 'characters'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Character.objects.select_related('user')
        
        # Apply search filter
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(character_class__icontains=search_query) |
                Q(user__username__icontains=search_query) |
                Q(user__name__icontains=search_query)
            )
        
        # Apply filters
        character_class = self.request.GET.get('character_class', '')
        if character_class:
            queryset = queryset.filter(character_class=character_class)
        
        
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        # Apply ordering
        ordering = self.request.GET.get('ordering', 'name')
        if ordering in ['name', '-name', 'level', '-level', 'created_at', '-created_at']:
            queryset = queryset.order_by(ordering)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = CharacterSearchForm(self.request.GET)
        context['character_classes'] = Character.objects.values_list('character_class', flat=True).distinct()
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'character_class': self.request.GET.get('character_class', ''),
            'status': self.request.GET.get('status', ''),
            'ordering': self.request.GET.get('ordering', 'name'),
        }
        return context


class CharacterListHTMXView(LoginRequiredMixin, View):
    """HTMX partial view for character list"""
    
    def get(self, request):
        # Use the same logic as CharacterListView
        queryset = Character.objects.select_related('user')
        
        # Apply search filter
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(character_class__icontains=search_query) |
                Q(user__username__icontains=search_query) |
                Q(user__name__icontains=search_query)
            )
        
        # Apply filters
        character_class = request.GET.get('character_class', '')
        if character_class:
            queryset = queryset.filter(character_class=character_class)
        
        
        status = request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        # Apply ordering
        ordering = request.GET.get('ordering', 'name')
        if ordering in ['name', '-name', 'level', '-level', 'created_at', '-created_at']:
            queryset = queryset.order_by(ordering)
        
        # Paginate results
        paginator = Paginator(queryset, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        return render(request, 'raiders/partials/character_list_partial.html', {
            'characters': page_obj,
            'page_obj': page_obj,
        })


class CharacterDetailView(LoginRequiredMixin, DetailView):
    """Character detail view"""
    model = Character
    template_name = 'raiders/character_detail.html'
    context_object_name = 'character'
    
    def get_queryset(self):
        return Character.objects.select_related('user')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        character = self.get_object()
        context['ownership_history'] = character.ownership_history.select_related(
            'previous_owner', 'new_owner', 'transferred_by'
        )[:10]  # Show last 10 transfers
        return context


class CharacterCreateView(LoginRequiredMixin, CreateView):
    """Character creation view"""
    model = Character
    form_class = CharacterForm
    template_name = 'raiders/character_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        
        # Create ownership record
        CharacterOwnership.record_transfer(
            character=self.object,
            new_owner=self.request.user,
            reason='created',
            notes=f'Character created by {self.request.user.username}',
            transferred_by=self.request.user
        )
        
        messages.success(self.request, f'Character "{self.object.name}" created successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('raiders:character-detail', kwargs={'pk': self.object.pk})


class CharacterCreateHTMXView(LoginRequiredMixin, View):
    """HTMX view for character creation"""
    
    def get(self, request):
        form = CharacterForm(user=request.user)
        return render(request, 'raiders/partials/character_form_partial.html', {
            'form': form,
            'action_url': reverse_lazy('raiders:character-create-htmx'),
        })
    
    def post(self, request):
        form = CharacterForm(request.POST, user=request.user)
        if form.is_valid():
            character = form.save(commit=False)
            character.user = request.user
            character.save()
            
            # Create ownership record
            CharacterOwnership.record_transfer(
                character=character,
                new_owner=request.user,
                reason='created',
                notes=f'Character created by {request.user.username}',
                transferred_by=request.user
            )
            
            messages.success(request, f'Character "{character.name}" created successfully!')
            
            # Return success response for HTMX
            return render(request, 'raiders/partials/character_form_success.html', {
                'character': character,
            })
        
        return render(request, 'raiders/partials/character_form_partial.html', {
            'form': form,
            'action_url': reverse_lazy('raiders:character-create-htmx'),
        })


class CharacterEditView(LoginRequiredMixin, UpdateView):
    """Character edit view"""
    model = Character
    form_class = CharacterForm
    template_name = 'raiders/character_form.html'
    
    def get_queryset(self):
        queryset = Character.objects.select_related('user')
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, f'Character "{self.object.name}" updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('raiders:character-detail', kwargs={'pk': self.object.pk})


class CharacterEditHTMXView(LoginRequiredMixin, View):
    """HTMX view for character editing"""
    
    def get_object(self):
        pk = self.kwargs.get('pk')
        queryset = Character.objects.select_related('user')
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return get_object_or_404(queryset, pk=pk)
    
    def get(self, request, pk):
        character = self.get_object()
        form = CharacterForm(instance=character, user=request.user)
        return render(request, 'raiders/partials/character_form_partial.html', {
            'form': form,
            'character': character,
            'action_url': reverse_lazy('raiders:character-edit-htmx', kwargs={'pk': pk}),
        })
    
    def post(self, request, pk):
        character = self.get_object()
        form = CharacterForm(request.POST, instance=character, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Character "{character.name}" updated successfully!')
            
            # Return success response for HTMX
            return render(request, 'raiders/partials/character_form_success.html', {
                'character': character,
            })
        
        return render(request, 'raiders/partials/character_form_partial.html', {
            'form': form,
            'character': character,
            'action_url': reverse_lazy('raiders:character-edit-htmx', kwargs={'pk': pk}),
        })


class CharacterDeleteView(LoginRequiredMixin, DeleteView):
    """Character deletion view"""
    model = Character
    template_name = 'raiders/character_confirm_delete.html'
    success_url = reverse_lazy('raiders:character-list')
    
    def get_queryset(self):
        queryset = Character.objects.select_related('user')
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, f'Character "{self.object.name}" deleted successfully!')
        return super().delete(request, *args, **kwargs)


class CharacterDeleteHTMXView(LoginRequiredMixin, View):
    """HTMX view for character deletion"""
    
    def get_object(self):
        pk = self.kwargs.get('pk')
        queryset = Character.objects.select_related('user')
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return get_object_or_404(queryset, pk=pk)
    
    def get(self, request, pk):
        character = self.get_object()
        return render(request, 'raiders/partials/character_delete_partial.html', {
            'character': character,
            'action_url': reverse_lazy('raiders:character-delete-htmx', kwargs={'pk': pk}),
        })
    
    def post(self, request, pk):
        character = self.get_object()
        character_name = character.name
        character.delete()
        messages.success(request, f'Character "{character_name}" deleted successfully!')
        
        # Return success response for HTMX
        return render(request, 'raiders/partials/character_delete_success.html', {
            'character_name': character_name,
        })


class CharacterSearchView(LoginRequiredMixin, View):
    """HTMX search view for characters"""
    
    def get(self, request):
        query = request.GET.get('q', '')
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        characters = Character.objects.filter(
            Q(name__icontains=query) |
            Q(character_class__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__name__icontains=query)
        ).select_related('user')[:10]
        
        results = []
        for character in characters:
            results.append({
                'id': character.id,
                'name': character.name,
                'character_class': character.character_class,
                'level': character.level,
                'user': character.user.name or character.user.username,
                'url': reverse_lazy('raiders:character-detail', kwargs={'pk': character.pk}),
            })
        
        return JsonResponse({'results': results})


# ==================== GUILD ROSTER VIEWS ====================

class GuildRosterView(LoginRequiredMixin, TemplateView):
    """Main guild roster dashboard view"""
    template_name = 'raiders/guild_roster.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get member counts by role
        member_counts = {
            'total': User.objects.count(),
            'officers': User.objects.filter(role_group='officer').count(),
            'members': User.objects.filter(role_group='member').count(),
            'applicants': User.objects.filter(role_group='applicant').count(),
        }
        
        # Get character counts
        character_counts = {
            'total': Character.objects.count(),
            'active': Character.objects.filter(status='active').count(),
        }
        
        # Get rank information
        ranks = Rank.objects.order_by('level')
        
        # Recent activity (latest characters)
        recent_characters = Character.objects.select_related('user').order_by('-created_at')[:5]
        
        # Recent ownership changes
        recent_transfers = CharacterOwnership.objects.select_related(
            'character', 'previous_owner', 'new_owner'
        ).order_by('-transfer_date')[:5]
        
        context.update({
            'member_counts': member_counts,
            'character_counts': character_counts,
            'ranks': ranks,
            'recent_characters': recent_characters,
            'recent_transfers': recent_transfers,
        })
        
        return context


class GuildRosterHTMXView(LoginRequiredMixin, View):
    """HTMX partial view for guild roster dashboard updates"""
    
    def get(self, request):
        # Get updated stats
        member_counts = {
            'total': User.objects.count(),
            'officers': User.objects.filter(role_group='officer').count(),
            'members': User.objects.filter(role_group='member').count(),
            'applicants': User.objects.filter(role_group='applicant').count(),
        }
        
        character_counts = {
            'total': Character.objects.count(),
            'active': Character.objects.filter(status='active').count(),
        }
        
        return render(request, 'raiders/partials/roster_stats_partial.html', {
            'member_counts': member_counts,
            'character_counts': character_counts,
        })


class MemberListView(LoginRequiredMixin, ListView):
    """Member list view"""
    model = User
    template_name = 'raiders/member_list.html'
    context_object_name = 'members'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = User.objects.select_related().prefetch_related('characters')
        
        # Apply search filter
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(discord_username__icontains=search_query)
            )
        
        # Apply filters
        role = self.request.GET.get('role', '')
        if role:
            queryset = queryset.filter(role_group=role)
        
        activity = self.request.GET.get('activity', '')
        if activity == 'active':
            queryset = queryset.filter(is_active=True)
        elif activity == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Apply ordering
        ordering = self.request.GET.get('ordering', 'name')
        if ordering in ['name', '-name', 'username', '-username', 'date_joined', '-date_joined']:
            queryset = queryset.order_by(ordering)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = MemberSearchForm(self.request.GET)
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'role': self.request.GET.get('role', ''),
            'activity': self.request.GET.get('activity', ''),
            'ordering': self.request.GET.get('ordering', 'name'),
        }
        return context


class MemberListHTMXView(LoginRequiredMixin, View):
    """HTMX partial view for member list"""
    
    def get(self, request):
        # Use the same logic as MemberListView
        queryset = User.objects.select_related().prefetch_related('characters')
        
        # Apply search filter
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(discord_username__icontains=search_query)
            )
        
        # Apply filters
        role = request.GET.get('role', '')
        if role:
            queryset = queryset.filter(role_group=role)
        
        activity = request.GET.get('activity', '')
        if activity == 'active':
            queryset = queryset.filter(is_active=True)
        elif activity == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Apply ordering
        ordering = request.GET.get('ordering', 'name')
        if ordering in ['name', '-name', 'username', '-username', 'date_joined', '-date_joined']:
            queryset = queryset.order_by(ordering)
        
        # Paginate results
        paginator = Paginator(queryset, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        return render(request, 'raiders/partials/member_list_partial.html', {
            'members': page_obj,
            'page_obj': page_obj,
        })


# ==================== RANK MANAGEMENT VIEWS ====================

class RankListView(LoginRequiredMixin, ListView):
    """Rank list view"""
    model = Rank
    template_name = 'raiders/rank_list.html'
    context_object_name = 'ranks'
    
    def get_queryset(self):
        return Rank.objects.order_by('level')


class RankDetailView(LoginRequiredMixin, DetailView):
    """Rank detail view"""
    model = Rank
    template_name = 'raiders/rank_detail.html'
    context_object_name = 'rank'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rank = self.get_object()
        # Characters no longer have ranks, so this section is empty
        context['characters'] = Character.objects.none()
        return context


class RankCreateView(LoginRequiredMixin, CreateView):
    """Rank creation view (staff only)"""
    model = Rank
    form_class = RankForm
    template_name = 'raiders/rank_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'You must be staff to manage ranks.')
            return redirect('raiders:rank-list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, f'Rank "{form.instance.name}" created successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('raiders:rank-detail', kwargs={'pk': self.object.pk})


class RankEditView(LoginRequiredMixin, UpdateView):
    """Rank edit view (staff only)"""
    model = Rank
    form_class = RankForm
    template_name = 'raiders/rank_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'You must be staff to manage ranks.')
            return redirect('raiders:rank-list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, f'Rank "{self.object.name}" updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('raiders:rank-detail', kwargs={'pk': self.object.pk})


class RankDeleteView(LoginRequiredMixin, DeleteView):
    """Rank deletion view (staff only)"""
    model = Rank
    template_name = 'raiders/rank_confirm_delete.html'
    success_url = reverse_lazy('raiders:rank-list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'You must be staff to manage ranks.')
            return redirect('raiders:rank-list')
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, f'Rank "{self.object.name}" deleted successfully!')
        return super().delete(request, *args, **kwargs)


# ==================== HTMX RANK MANAGEMENT VIEWS ====================

class RankCreateHTMXView(LoginRequiredMixin, View):
    """HTMX view for rank creation"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        form = RankForm()
        return render(request, 'raiders/partials/rank_form_partial.html', {
            'form': form,
            'action_url': reverse_lazy('raiders:rank-create-htmx'),
        })
    
    def post(self, request):
        form = RankForm(request.POST)
        if form.is_valid():
            rank = form.save()
            messages.success(request, f'Rank "{rank.name}" created successfully!')
            
            # Return success response for HTMX
            return render(request, 'raiders/partials/rank_form_success.html', {
                'rank': rank,
            })
        
        return render(request, 'raiders/partials/rank_form_partial.html', {
            'form': form,
            'action_url': reverse_lazy('raiders:rank-create-htmx'),
        })


class RankEditHTMXView(LoginRequiredMixin, View):
    """HTMX view for rank editing"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        pk = self.kwargs.get('pk')
        return get_object_or_404(Rank, pk=pk)
    
    def get(self, request, pk):
        rank = self.get_object()
        form = RankForm(instance=rank)
        return render(request, 'raiders/partials/rank_form_partial.html', {
            'form': form,
            'rank': rank,
            'action_url': reverse_lazy('raiders:rank-edit-htmx', kwargs={'pk': pk}),
        })
    
    def post(self, request, pk):
        rank = self.get_object()
        form = RankForm(request.POST, instance=rank)
        if form.is_valid():
            form.save()
            messages.success(request, f'Rank "{rank.name}" updated successfully!')
            
            # Return success response for HTMX
            return render(request, 'raiders/partials/rank_form_success.html', {
                'rank': rank,
            })
        
        return render(request, 'raiders/partials/rank_form_partial.html', {
            'form': form,
            'rank': rank,
            'action_url': reverse_lazy('raiders:rank-edit-htmx', kwargs={'pk': pk}),
        })


class RankDeleteHTMXView(LoginRequiredMixin, View):
    """HTMX view for rank deletion"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        pk = self.kwargs.get('pk')
        return get_object_or_404(Rank, pk=pk)
    
    def get(self, request, pk):
        rank = self.get_object()
        return render(request, 'raiders/partials/rank_delete_partial.html', {
            'rank': rank,
            'action_url': reverse_lazy('raiders:rank-delete-htmx', kwargs={'pk': pk}),
        })
    
    def post(self, request, pk):
        rank = self.get_object()
        rank_name = rank.name
        character_count = 0  # Characters no longer have ranks
        rank.delete()
        messages.success(request, f'Rank "{rank_name}" deleted successfully!')
        
        # Return success response for HTMX
        return render(request, 'raiders/partials/rank_delete_success.html', {
            'rank_name': rank_name,
            'character_count': character_count,
        })