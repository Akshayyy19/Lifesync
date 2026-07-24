from django import forms

from .models import DiaryEntry


class DiaryEntryForm(forms.ModelForm):
    class Meta:
        model = DiaryEntry
        fields = ['title', 'content', 'mood', 'date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Optional — leave blank to use the date',
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 10, 'placeholder': "What's on your mind today?",
            }),
            'mood': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
