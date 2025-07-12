from django import forms
from django.contrib.auth import get_user_model
from .models import Character, Rank, CharacterOwnership

User = get_user_model()


class CharacterForm(forms.ModelForm):
    """Form for creating and editing characters"""
    
    class Meta:
        model = Character
        fields = ['name', 'character_class', 'level', 'status', 'main_character', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'Enter character name'
            }),
            'character_class': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'e.g., Warrior, Cleric, Wizard'
            }),
            'level': forms.NumberInput(attrs={
                'class': 'form-input w-full',
                'min': 1,
                'max': 70
            }),
            'status': forms.Select(attrs={
                'class': 'form-select w-full'
            }),
            'main_character': forms.Select(attrs={
                'class': 'form-select w-full'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea w-full',
                'rows': 3,
                'placeholder': 'Optional character description or notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set up main character choices (only main characters of the current user)
        if user:
            self.fields['main_character'].queryset = Character.objects.filter(
                user=user,
                main_character__isnull=True
            )
        elif self.instance.pk:
            # For editing, show main characters of the same user
            self.fields['main_character'].queryset = Character.objects.filter(
                user=self.instance.user,
                main_character__isnull=True
            ).exclude(pk=self.instance.pk)
        else:
            self.fields['main_character'].queryset = Character.objects.none()
        
        # Add empty choice for main character
        self.fields['main_character'].empty_label = "Main Character (no alt relationship)"
        
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip().title()
            # Check for duplicate names (excluding current instance)
            queryset = Character.objects.filter(name=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(f'A character with the name "{name}" already exists.')
        return name
    
    def clean_level(self):
        level = self.cleaned_data.get('level')
        if level is not None and (level < 1 or level > 70):
            raise forms.ValidationError('Level must be between 1 and 70.')
        return level
    
    def clean_main_character(self):
        main_character = self.cleaned_data.get('main_character')
        
        # If this is an edit and the character is currently a main character
        if self.instance.pk and self.instance.is_main and main_character:
            # Check if any characters are alts of this character
            if self.instance.alt_characters.exists():
                raise forms.ValidationError(
                    'Cannot set this character as an alt because it currently has alt characters. '
                    'Please reassign those alts first.'
                )
        
        # Cannot set self as main character
        if main_character and self.instance.pk and main_character.pk == self.instance.pk:
            raise forms.ValidationError('A character cannot be its own main character.')
        
        return main_character


class CharacterSearchForm(forms.Form):
    """Form for searching and filtering characters"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full',
            'placeholder': 'Search characters...',
            'hx-get': '',
            'hx-trigger': 'keyup changed delay:300ms',
            'hx-target': '#character-list',
        })
    )
    
    character_class = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full',
            'placeholder': 'Filter by class...',
        })
    )
    
    TYPE_CHOICES = [
        ('', 'All Characters'),
        ('main', 'Main Characters'),
        ('alt', 'Alt Characters'),
    ]
    
    type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Character.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )
    
    ORDERING_CHOICES = [
        ('name', 'Name (A-Z)'),
        ('-name', 'Name (Z-A)'),
        ('level', 'Level (Low to High)'),
        ('-level', 'Level (High to Low)'),
        ('created_at', 'Created (Oldest First)'),
        ('-created_at', 'Created (Newest First)'),
    ]
    
    ordering = forms.ChoiceField(
        choices=ORDERING_CHOICES,
        required=False,
        initial='name',
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )


class CharacterTransferForm(forms.Form):
    """Form for transferring character ownership (staff only)"""
    
    character = forms.ModelChoiceField(
        queryset=Character.objects.select_related('user'),
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )
    
    new_owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )
    
    reason = forms.ChoiceField(
        choices=CharacterOwnership.TRANSFER_REASONS,
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea w-full',
            'rows': 3,
            'placeholder': 'Optional notes about the transfer...'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        character = cleaned_data.get('character')
        new_owner = cleaned_data.get('new_owner')
        
        if character and new_owner:
            if character.user == new_owner:
                raise forms.ValidationError('Character is already owned by this user.')
        
        return cleaned_data


class RankForm(forms.ModelForm):
    """Form for creating and editing ranks"""
    
    class Meta:
        model = Rank
        fields = ['name', 'level', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'placeholder': 'Enter rank name'
            }),
            'level': forms.NumberInput(attrs={
                'class': 'form-input w-full',
                'min': 0,
                'max': 100
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea w-full',
                'rows': 3,
                'placeholder': 'Description of rank permissions and responsibilities'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-input w-full',
                'type': 'color',
                'placeholder': '#000000'
            }),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip().title()
            # Check for duplicate names (excluding current instance)
            queryset = Rank.objects.filter(name=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(f'A rank with the name "{name}" already exists.')
        return name
    
    def clean_level(self):
        level = self.cleaned_data.get('level')
        if level is not None:
            # Check for duplicate levels (excluding current instance)
            queryset = Rank.objects.filter(level=level)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(f'A rank with level {level} already exists.')
        return level


class MemberSearchForm(forms.Form):
    """Form for searching and filtering guild members"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full',
            'placeholder': 'Search members...',
            'hx-get': '',
            'hx-trigger': 'keyup changed delay:300ms',
            'hx-target': '#member-list',
        })
    )
    
    
    ROLE_CHOICES = [
        ('', 'All Roles'),
        ('developer', 'Developer'),
        ('officer', 'Officer'),
        ('recruiter', 'Recruiter'),
        ('member', 'Member'),
        ('applicant', 'Applicant'),
        ('guest', 'Guest'),
    ]
    
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )
    
    ACTIVITY_CHOICES = [
        ('', 'All Members'),
        ('active', 'Active Members'),
        ('inactive', 'Inactive Members'),
    ]
    
    activity = forms.ChoiceField(
        choices=ACTIVITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )
    
    ORDERING_CHOICES = [
        ('name', 'Name (A-Z)'),
        ('-name', 'Name (Z-A)'),
        ('username', 'Username (A-Z)'),
        ('-username', 'Username (Z-A)'),
        ('date_joined', 'Joined (Oldest First)'),
        ('-date_joined', 'Joined (Newest First)'),
    ]
    
    ordering = forms.ChoiceField(
        choices=ORDERING_CHOICES,
        required=False,
        initial='name',
        widget=forms.Select(attrs={
            'class': 'form-select w-full'
        })
    )