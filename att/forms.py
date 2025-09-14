#!/usr/bin/env python

from django import forms
from .models import AcademicYear

class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'})
        }
