from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from weather.services import get_current_weather

from .forms import DiaryEntryForm
from .models import DiaryEntry


@login_required
def diary_list(request):
    entries = DiaryEntry.objects.filter(user=request.user)
    return render(request, 'diary/diary_list.html', {'entries': entries})


@login_required
def diary_detail(request, pk):
    entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)
    return render(request, 'diary/diary_detail.html', {'entry': entry})


@login_required
def diary_create(request):
    if request.method == 'POST':
        form = DiaryEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            _attach_weather_snapshot(entry, request.user)
            entry.save()
            messages.success(request, 'Your diary entry was saved.')
            return redirect('diary:detail', pk=entry.pk)
    else:
        form = DiaryEntryForm(initial={'date': timezone.localdate()})

    return render(request, 'diary/diary_form.html', {'form': form, 'action': 'New'})


@login_required
def diary_update(request, pk):
    entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)

    if request.method == 'POST':
        form = DiaryEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your diary entry was updated.')
            return redirect('diary:detail', pk=entry.pk)
    else:
        form = DiaryEntryForm(instance=entry)

    return render(request, 'diary/diary_form.html', {'form': form, 'action': 'Edit', 'entry': entry})


@login_required
def diary_delete(request, pk):
    entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)

    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Diary entry deleted.')
        return redirect('diary:list')

    return render(request, 'diary/diary_confirm_delete.html', {'entry': entry})


def _attach_weather_snapshot(entry, user):
    """Best-effort: silently skip if the API/profile isn't available."""
    try:
        city = user.profile.city
        weather = get_current_weather(city)
        if weather:
            entry.weather_temp = weather.get('temp')
            entry.weather_condition = weather.get('description')
    except Exception:
        pass
