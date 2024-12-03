from django import forms
from .models import Checklist


class ChecklistForm(forms.ModelForm):
    class Meta:
        model = Checklist
        fields = ['list_name', 'status']