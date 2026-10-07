from django import forms

from .models import Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'category', 'date', 'time',
            'venue_type', 'location', 'remind_before_minutes',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Project submission',
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'venue_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_venue_type'}),
            'location': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Optional (e.g. Lords Ground, Marriott, Mumbai)',
            }),
            'remind_before_minutes': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Birthdays don't need a specific clock time.
        if cleaned_data.get('category') == 'birthday':
            cleaned_data['time'] = None
        return cleaned_data
