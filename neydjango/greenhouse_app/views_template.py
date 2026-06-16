"""
greenhouse_app/views_template.py

Django template-based views (HTML responses).
These views serve the HTML templates we just created.
They are SEPARATE from the DRF API views in views.py,
which continue to serve JSON for the Next.js frontend.

Add these to greenhouse_app/views.py or keep in a separate file
and import into urls.py.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.views.decorators.http import require_POST
from django import forms
from accounts.models import GreenhouseMembership
from .models import Greenhouse, House, Bed, Crop
from django.contrib.auth.forms import UserCreationForm
from accounts.models import User
from django.contrib.auth import update_session_auth_hash

# ── Auth Views ────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('greenhouse_app:greenhouse_list')

    # Re-use Django's built-in AuthenticationForm for validation
    from django.contrib.auth.forms import AuthenticationForm
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect(request.GET.get('next', 'greenhouse_app:greenhouse_list'))

    return render(request, 'greenhouse_app/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('greenhouse_app:login')


# ── Greenhouse ────────────────────────────────────────────────────────────────

@login_required
def greenhouse_list(request):
    greenhouses = Greenhouse.objects.filter(
        memberships__user=request.user,
    ).distinct()

    # Sum area from all Houses across all greenhouses
    from django.db.models import Sum

    
    # Attach area directly to each greenhouse object
    for gh in greenhouses:
        area = gh.houses.aggregate(total=Sum('area_m2'))['total']
        gh.computed_area = int(area) if area else None

    total_area = sum(gh.computed_area for gh in greenhouses if gh.computed_area)

    memberships = GreenhouseMembership.objects.filter(
        user=request.user
    ).values_list('role', flat=True)

    role_priority = ['owner', 'manager', 'operator', 'consultant', 'guest']
    user_role = 'guest'
    for role in role_priority:
        if role in memberships:
            user_role = role
            break

    context = {
        'greenhouses': greenhouses,
        'total_area': total_area if total_area else None,
        'total_active_crops': Crop.objects.filter(
            bed__house__greenhouse__in=greenhouses,
            status='growing',
        ).count(),
        'user_role': user_role,
    }
    return render(request, 'greenhouse_app/greenhouse_list.html', context)


@login_required
def greenhouse_detail(request, greenhouse_id):
    greenhouse = get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
    )
    houses = greenhouse.houses.all().prefetch_related('beds__crops')

    # Sum area from all houses in this greenhouse
    from django.db.models import Sum
    total_area = greenhouse.houses.aggregate(total=Sum('area_m2'))['total']

    total_beds = sum(h.beds.count() for h in houses)
    active_crops = Crop.objects.filter(
        bed__house__greenhouse=greenhouse,
        status='growing',
    ).count()

    return render(request, 'greenhouse_app/greenhouse_detail.html', {
        'greenhouse': greenhouse,
        'houses': houses,
        'total_beds': total_beds,
        'active_crops': active_crops,
        'total_area': int(total_area) if total_area else None,
    })


@login_required
def greenhouse_create(request):
    class GreenhouseForm(forms.ModelForm):
        class Meta:
            model = Greenhouse
            fields = ['name', 'description', 'location_geojson', 'timezone']

    if request.method == 'POST':
        form = GreenhouseForm(request.POST)
        if form.is_valid():
            gh = form.save(commit=False)
            gh.owner = request.user
            gh.save()
            from accounts.models import GreenhouseMembership
            GreenhouseMembership.objects.create(
                greenhouse=gh, user=request.user, role=GreenhouseMembership.Role.OWNER
            )
            messages.success(request, f'Greenhouse "{gh.name}" created.')
            return redirect('greenhouse_app:greenhouse_detail', greenhouse_id=gh.id)
    else:
        form = GreenhouseForm()

    return render(request, 'greenhouse_app/form.html', {
        'form': form,
        'form_title': 'گلخانه جدید',
        'form_subtitle': 'تعریف تاسیسات پرورش جدید',
        'submit_label': 'ایجاد گلخانه',
        'cancel_url': '/greenhouse_app/greenhouses/',
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': 'ایجاد گلخانه', 'url': None},
        ],
    })


@login_required
def greenhouse_edit(request, greenhouse_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id)

    class GreenhouseForm(forms.ModelForm):
        class Meta:
            model = Greenhouse
            fields = ['name', 'description', 'location_geojson', 'timezone', 'is_active']

    if request.method == 'POST':
        form = GreenhouseForm(request.POST, instance=greenhouse)
        if form.is_valid():
            form.save()
            messages.success(request, 'Greenhouse updated.')
            return redirect('greenhouse_app:greenhouse_detail', greenhouse_id=greenhouse.id)
    else:
        form = GreenhouseForm(instance=greenhouse)

    return render(request, 'greenhouse_app/form.html', {
        'form': form,
        'greenhouse': greenhouse,
        'form_title': f'ویرایش {greenhouse.name}',
        'submit_label': 'ذخیره تغییرات',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/',
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'ویرایش', 'url': None},
        ],
    })


# ── House ─────────────────────────────────────────────────────────────────────

@login_required
def house_detail(request, greenhouse_id, house_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    beds  = house.beds.all().prefetch_related('crops')
    return render(request, 'greenhouse_app/house_detail.html', {
        'greenhouse': greenhouse, 'house': house, 'beds': beds,
    })


@login_required
def house_create(request, greenhouse_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)

    class HouseForm(forms.ModelForm):
        class Meta:
            model = House
            fields = ['name', 'area_m2', 'notes']

        def clean_name(self):
            name = self.cleaned_data.get('name')
            # Check if this greenhouse already has a house with this name
            if name and House.objects.filter(greenhouse=greenhouse, name=name).exists():
                raise forms.ValidationError("سالنی با این نام در این گلخانه قبلاً ثبت شده است، لطفاً نام دیگری انتخاب کنید.")
            return name

    if request.method == 'POST':
        form = HouseForm(request.POST)
        if form.is_valid():
            house = form.save(commit=False)
            house.greenhouse = greenhouse
            house.save()
            messages.success(request, f'House "{house.name}" created.')
            return redirect('greenhouse_app:greenhouse_detail', greenhouse_id=greenhouse.id)
    else:
        form = HouseForm()

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'افزودن سالن به {greenhouse.name}',
        'submit_label': 'ایجاد سالن',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/',
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'افزودن سالن', 'url': None},
        ],
    })


@login_required
def house_edit(request, greenhouse_id, house_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)

    class HouseForm(forms.ModelForm):
        class Meta:
            model = House
            fields = ['name', 'area_m2', 'notes']

        def clean_name(self):
            name = self.cleaned_data.get('name')
            # Check for duplicates, excluding the current house instance being edited
            if name and House.objects.filter(greenhouse=greenhouse, name=name).exclude(id=house.id).exists():
                raise forms.ValidationError("سالنی با این نام در این گلخانه قبلاً ثبت شده است، لطفاً نام دیگری انتخاب کنید.")
            return name

    if request.method == 'POST':
        form = HouseForm(request.POST, instance=house)
        if form.is_valid():
            form.save()
            messages.success(request, 'House updated.')
            return redirect('greenhouse_app:house_detail',
                            greenhouse_id=greenhouse.id, house_id=house.id)
    else:
        form = HouseForm(instance=house)

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'ویرایش {house.name}',
        'submit_label': 'ذخیره تغییرات',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': house.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/'},
            {'label': 'ویرایش', 'url': None},
        ],
    })


# ── Bed ───────────────────────────────────────────────────────────────────────

@login_required
def bed_detail(request, greenhouse_id, house_id, bed_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    house  = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    bed    = get_object_or_404(Bed, id=bed_id, house=house)
    crops  = bed.crops.all().order_by('-planted_at')
    active = crops.filter(status='growing').first()

    return render(request, 'greenhouse_app/bed_detail.html', {
        'greenhouse': greenhouse, 'house': house, 'bed': bed,
        'crops': crops, 'active_crop': active,
    })


@login_required
def bed_create(request, greenhouse_id, house_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)

    class BedForm(forms.ModelForm):
        class Meta:
            model = Bed
            fields = ['code', 'area_m2', 'capacity', 'notes']

        # Custom validation to check for duplicate bed names in this house
        def clean_code(self):
            code = self.cleaned_data.get('code')
            if code and Bed.objects.filter(house=house, code=code).exists():
                raise forms.ValidationError("بستری با این شناسه در این سالن قبلاً ثبت شده است، لطفاً نام دیگری انتخاب کنید.")
            return code
        
    if request.method == 'POST':
        form = BedForm(request.POST)
        if form.is_valid():
            bed = form.save(commit=False)
            bed.house = house
            bed.save()
            messages.success(request, f'Bed "{bed.code}" created.')
            return redirect('greenhouse_app:house_detail',
                            greenhouse_id=greenhouse.id, house_id=house.id)
    else:
        form = BedForm()

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'افزودن بستر به {house.name}',
        'submit_label': 'ایجاد بستر',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': house.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/'},
            {'label': 'افزودن بستر', 'url': None},
        ],
    })


@login_required
def bed_edit(request, greenhouse_id, house_id, bed_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    bed   = get_object_or_404(Bed, id=bed_id, house=house)

    class BedForm(forms.ModelForm):
        class Meta:
            model = Bed
            fields = ['code', 'area_m2', 'capacity', 'notes']

        def clean_code(self):
            code = self.cleaned_data.get('code')
            # Check for duplicates, excluding the current bed instance being edited
            if code and Bed.objects.filter(house=house, code=code).exclude(id=bed.id).exists():
                raise forms.ValidationError("بستری با این شناسه در این سالن قبلاً ثبت شده است، لطفاً نام دیگری انتخاب کنید.")
            return code

    if request.method == 'POST':
        form = BedForm(request.POST, instance=bed)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bed updated.')
            return redirect('greenhouse_app:bed_detail',
                            greenhouse_id=greenhouse.id, house_id=house.id, bed_id=bed.id)
    else:
        form = BedForm(instance=bed)

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'ویرایش بستر {bed.code}',
        'submit_label': 'ذخیره تغییرات',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/beds/{bed.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': house.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/'},
            {'label': bed.code, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/beds/{bed.id}/'},
            {'label': 'ویرایش', 'url': None},
        ],
    })


# ── Crop ──────────────────────────────────────────────────────────────────────

@login_required
def crop_create(request, greenhouse_id, house_id, bed_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    bed   = get_object_or_404(Bed, id=bed_id, house=house)

    class CropForm(forms.ModelForm):
        class Meta:
            model = Crop
            fields = ['crop_type', 'variety', 'planted_at', 'expected_harvest_at',
                      'status', 'plant_count', 'notes']
            widgets = {
                'planted_at': forms.DateInput(attrs={'type': 'date'}),
                'expected_harvest_at': forms.DateInput(attrs={'type': 'date'}),
            }

    if request.method == 'POST':
        form = CropForm(request.POST)
        if form.is_valid():
            crop = form.save(commit=False)
            crop.bed = bed
            crop.created_by = request.user
            crop.save()
            messages.success(request, f'Crop cycle "{crop.crop_type}" started.')
            return redirect('greenhouse_app:bed_detail',
                            greenhouse_id=greenhouse.id, house_id=house.id, bed_id=bed.id)
    else:
        form = CropForm()

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'دوره کاشت جدید — بستر {bed.code}',
        'form_subtitle': f'{greenhouse.name} / {house.name}',
        'submit_label': 'شروع دوره کاشت',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/beds/{bed.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': house.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/'},
            {'label': bed.code, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/beds/{bed.id}/'},
            {'label': 'محصول جدید', 'url': None},
        ],
    })


@login_required
def crop_edit(request, greenhouse_id, house_id, bed_id, crop_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    bed   = get_object_or_404(Bed, id=bed_id, house=house)
    crop  = get_object_or_404(Crop, id=crop_id, bed=bed)

    class CropForm(forms.ModelForm):
        class Meta:
            model = Crop
            fields = ['crop_type', 'variety', 'planted_at', 'expected_harvest_at',
                      'actual_harvest_at', 'status', 'plant_count', 'notes']
            widgets = {
                'planted_at': forms.DateInput(attrs={'type': 'date'}),
                'expected_harvest_at': forms.DateInput(attrs={'type': 'date'}),
                'actual_harvest_at': forms.DateInput(attrs={'type': 'date'}),
            }

    if request.method == 'POST':
        form = CropForm(request.POST, instance=crop)
        if form.is_valid():
            form.save()
            messages.success(request, 'Crop cycle updated.')
            return redirect('greenhouse_app:bed_detail',
                            greenhouse_id=greenhouse.id, house_id=house.id, bed_id=bed.id)
    else:
        form = CropForm(instance=crop)

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'ویرایش محصول — {crop.crop_type}',
        'submit_label': 'دخیره تغییرات',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/beds/{bed.id}/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': bed.code, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/houses/{house.id}/beds/{bed.id}/'},
            {'label': 'ویرایش محصول', 'url': None},
        ],
    })


# ── Members ───────────────────────────────────────────────────────────────────

@login_required
def member_list(request, greenhouse_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    members = greenhouse.memberships.all().select_related('user')
    my_role = greenhouse.memberships.get(user=request.user).role
    can_manage = my_role in (GreenhouseMembership.Role.OWNER, GreenhouseMembership.Role.MANAGER)

    return render(request, 'greenhouse_app/member_list.html', {
        'greenhouse': greenhouse,
        'members': members,
        'can_manage': can_manage,
    })


@login_required
def member_add(request, greenhouse_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user,)

    class MemberForm(forms.Form):
        username = forms.CharField(max_length=150)
        role = forms.ChoiceField(choices=GreenhouseMembership.Role.choices)

    if request.method == 'POST':
        form = MemberForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(username=form.cleaned_data['username'])
                GreenhouseMembership.objects.get_or_create(
                    greenhouse=greenhouse, user=user,
                    defaults={'role': form.cleaned_data['role']}
                )
                messages.success(request, f'{user.username} added as {form.cleaned_data["role"]}.')
                return redirect('greenhouse_app:member_list', greenhouse_id=greenhouse.id)
            except User.DoesNotExist:
                form.add_error('username', 'No user found with that username.')
    else:
        form = MemberForm()

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'افزودن عضو — {greenhouse.name}',
        'submit_label': 'افزودن عضو',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/members/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'عضوها', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/members/'},
            {'label': 'افزودن', 'url': None},
        ],
    })


@login_required
def member_edit(request, greenhouse_id, member_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    member = get_object_or_404(GreenhouseMembership, id=member_id, greenhouse=greenhouse)

    class RoleForm(forms.ModelForm):
        class Meta:
            model = GreenhouseMembership
            fields = ['role']

    if request.method == 'POST':
        form = RoleForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, 'Role updated.')
            return redirect('greenhouse_app:member_list', greenhouse_id=greenhouse.id)
    else:
        form = RoleForm(instance=member)

    return render(request, 'greenhouse_app/form.html', {
        'form': form, 'greenhouse': greenhouse,
        'form_title': f'تغییر نقش — {member.user.username}',
        'submit_label': 'بروزرسانی نقش',
        'cancel_url': f'/greenhouse_app/greenhouses/{greenhouse.id}/members/',
        'breadcrumbs': [
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'عضوها', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/members/'},
            {'label': 'ویرایش نقش', 'url': None},
        ],
    })


@require_POST
@login_required
def member_remove(request, greenhouse_id, member_id):
    greenhouse = get_object_or_404(Greenhouse, id=greenhouse_id,
                                   memberships__user=request.user)
    member = get_object_or_404(GreenhouseMembership, id=member_id, greenhouse=greenhouse)
    member.delete()
    messages.success(request, f'{member.user.username} removed from greenhouse.')
    return redirect('greenhouse_app:member_list', greenhouse_id=greenhouse.id)


# ── Register ───────────────────────────────────────────────────────────────────


def register_view(request):
    if request.user.is_authenticated:
        return redirect('greenhouse_app:greenhouse_list')

    class RegisterForm(forms.ModelForm):
        password1 = forms.CharField(
            label='Password',
            widget=forms.PasswordInput,
        )
        password2 = forms.CharField(
            label='Confirm Password',
            widget=forms.PasswordInput,
        )

        class Meta:
            model = User
            fields = ['username', 'email', 'first_name', 'last_name', 'phone']

        def clean(self):
            cleaned = super().clean()
            p1 = cleaned.get('password1')
            p2 = cleaned.get('password2')
            if p1 and p2 and p1 != p2:
                raise forms.ValidationError({'password2': 'Passwords do not match.'})
            return cleaned

        def save(self, commit=True):
            user = super().save(commit=False)
            user.set_password(self.cleaned_data['password1'])
            if commit:
                user.save()
            return user

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.username}! Your account has been created.')
            return redirect('greenhouse_app:greenhouse_list')
    else:
        form = RegisterForm()

    return render(request, 'greenhouse_app/register.html', {'form': form})


# ── Profile View ───────────────────────────────────────────────────────────────────


@login_required
def profile_view(request):
    from accounts.models import GreenhouseMembership
    from django.contrib.auth import update_session_auth_hash

    user = request.user
    password_error = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'profile':
            # Update personal info
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name  = request.POST.get('last_name', '').strip()
            user.email      = request.POST.get('email', '').strip()
            user.phone      = request.POST.get('phone', '').strip()
            user.locale     = request.POST.get('locale', 'fa')
            user.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('greenhouse_app:profile')

        elif form_type == 'password':
            old_password  = request.POST.get('old_password', '')
            new_password1 = request.POST.get('new_password1', '')
            new_password2 = request.POST.get('new_password2', '')

            if not user.check_password(old_password):
                password_error = 'Current password is incorrect.'
            elif new_password1 != new_password2:
                password_error = 'New passwords do not match.'
            elif len(new_password1) < 8:
                password_error = 'Password must be at least 8 characters.'
            else:
                user.set_password(new_password1)
                user.save()
                # Keep user logged in after password change
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')
                return redirect('greenhouse_app:profile')

    # Get all memberships with greenhouse data
    memberships = GreenhouseMembership.objects.filter(
        user=user
    ).select_related('greenhouse').order_by('joined_at')

    # Determine highest role
    role_priority = ['owner', 'manager', 'operator', 'consultant', 'guest']
    roles = list(memberships.values_list('role', flat=True))
    user_role = 'guest'
    for role in role_priority:
        if role in roles:
            user_role = role
            break

    return render(request, 'greenhouse_app/profile.html', {
        'memberships':    memberships,
        'user_role':      user_role,
        'password_error': password_error,
    })


# ── Delete Views ──────────────────────────────────────────────────────────────
# All deletes are POST-only and restricted to Owner and Manager roles.

ALLOWED_DELETE_ROLES = (
    GreenhouseMembership.Role.OWNER,
    GreenhouseMembership.Role.MANAGER,
)


@require_POST
@login_required
def greenhouse_delete(request, greenhouse_id):
    """
    Soft-delete a greenhouse. Sets is_active=False — data is preserved.
    Only the Owner or Manager of this greenhouse can do this.
    Redirects to the greenhouse list after deletion.
    """
    greenhouse = get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
    )

    membership = get_object_or_404(
        GreenhouseMembership,
        greenhouse=greenhouse,
        user=request.user,
    )

    if membership.role not in ALLOWED_DELETE_ROLES:
        messages.error(request, 'فقط مالک یا مدیر گلخانه می‌تواند آن را حذف کند.')
        return redirect('greenhouse_app:greenhouse_detail', greenhouse_id=greenhouse.id)

    name = greenhouse.name
    greenhouse.is_active = False
    greenhouse.save()
    greenhouse.delete()
    messages.success(request, f'گلخانه "{name}" غیرفعال و حذف شد.')
    return redirect('greenhouse_app:greenhouse_list')


@require_POST
@login_required
def house_delete(request, greenhouse_id, house_id):
    """
    Hard-delete a house and all its beds and crops (cascade).
    Only Owner or Manager of this greenhouse can do this.
    Redirects to the greenhouse detail page.
    """
    greenhouse = get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
    )

    membership = get_object_or_404(
        GreenhouseMembership,
        greenhouse=greenhouse,
        user=request.user,
    )

    if membership.role not in ALLOWED_DELETE_ROLES:
        messages.error(request, 'فقط مالک یا مدیر گلخانه می‌تواند سالن را حذف کند.')
        return redirect('greenhouse_app:greenhouse_detail', greenhouse_id=greenhouse.id)

    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    name = house.name
    house.delete()
    messages.success(request, f'سالن "{name}" و تمام بسترهای آن حذف شدند.')
    return redirect('greenhouse_app:greenhouse_detail', greenhouse_id=greenhouse.id)


@require_POST
@login_required
def bed_delete(request, greenhouse_id, house_id, bed_id):
    """
    Hard-delete a bed and all its crop cycles (cascade).
    Only Owner or Manager of this greenhouse can do this.
    Redirects to the house detail page.
    """
    greenhouse = get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
    )

    membership = get_object_or_404(
        GreenhouseMembership,
        greenhouse=greenhouse,
        user=request.user,
    )

    if membership.role not in ALLOWED_DELETE_ROLES:
        messages.error(request, 'فقط مالک یا مدیر گلخانه می‌تواند بستر را حذف کند.')
        return redirect('greenhouse_app:house_detail',
                        greenhouse_id=greenhouse.id, house_id=house_id)

    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    bed = get_object_or_404(Bed, id=bed_id, house=house)
    code = bed.code
    bed.delete()
    messages.success(request, f'بستر "{code}" و تمام دوره‌های کاشت آن حذف شدند.')
    return redirect('greenhouse_app:house_detail',
                    greenhouse_id=greenhouse.id, house_id=house.id)


@require_POST
@login_required
def crop_delete(request, greenhouse_id, house_id, bed_id, crop_id):
    """
    Hard-delete a crop cycle.
    Blocked if this crop has any sales records linked to it — deleting
    a crop with sales would break financial history.
    Only Owner or Manager of this greenhouse can do this.
    Redirects to the bed detail page.
    """
    greenhouse = get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
    )

    membership = get_object_or_404(
        GreenhouseMembership,
        greenhouse=greenhouse,
        user=request.user,
    )

    if membership.role not in ALLOWED_DELETE_ROLES:
        messages.error(request, 'فقط مالک یا مدیر گلخانه می‌تواند دوره کاشت را حذف کند.')
        return redirect('greenhouse_app:bed_detail',
                        greenhouse_id=greenhouse.id, house_id=house_id, bed_id=bed_id)

    house = get_object_or_404(House, id=house_id, greenhouse=greenhouse)
    bed = get_object_or_404(Bed, id=bed_id, house=house)
    crop = get_object_or_404(Crop, id=crop_id, bed=bed)

    # Guard: block deletion if sales records exist for this crop
    if crop.sales.exists():
        messages.error(
            request,
            f'دوره کاشت "{crop.crop_type}" دارای سوابق فروش است و نمی‌توان آن را حذف کرد. '
            'ابتدا فروش‌های مرتبط را حذف یا ویرایش کنید.'
        )
        return redirect('greenhouse_app:bed_detail',
                        greenhouse_id=greenhouse.id, house_id=house.id, bed_id=bed.id)

    crop_name = f'{crop.crop_type} ({crop.variety})' if crop.variety else crop.crop_type
    crop.delete()
    messages.success(request, f'دوره کاشت "{crop_name}" حذف شد.')
    return redirect('greenhouse_app:bed_detail',
                    greenhouse_id=greenhouse.id, house_id=house.id, bed_id=bed.id)