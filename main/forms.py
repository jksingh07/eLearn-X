from django import forms
from froala_editor.widgets import FroalaEditor
from .models import Announcement, Assignment, Material, Department, Course


class AnnouncementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(AnnouncementForm, self).__init__(*args, **kwargs)
        self.fields['description'].required = True
        self.fields['description'].label = ''

    class Meta:
        model = Announcement
        fields = ['description']
        widgets = {
            'description': FroalaEditor(),
        }


class AssignmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(AssignmentForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
            field.label = ''
        self.fields['file'].required = False

    class Meta:
        model = Assignment
        fields = ('title', 'description', 'deadline', 'marks', 'file')
        widgets = {
            'description': FroalaEditor(),
            'title': forms.TextInput(attrs={'class': 'form-control mt-1', 'id': 'title', 'name': 'title', 'placeholder': 'Title'}),
            'deadline': forms.DateTimeInput(attrs={'class': 'form-control mt-1', 'id': 'deadline', 'name': 'deadline', 'type': 'datetime-local'}),
            'marks': forms.NumberInput(attrs={'class': 'form-control mt-1', 'id': 'marks', 'name': 'marks', 'placeholder': 'Marks'}),
            'file': forms.FileInput(attrs={'class': 'form-control mt-1', 'id': 'file', 'name': 'file', 'aria-describedby': 'file', 'aria-label': 'Upload'}),
        }


class MaterialForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(MaterialForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
            field.label = ""
        self.fields['file'].required = False

    class Meta:
        model = Material
        fields = ('description', 'file')
        widgets = {
            'description': FroalaEditor(),
            'file': forms.FileInput(attrs={'class': 'form-control', 'id': 'file', 'name': 'file', 'aria-describedby': 'file', 'aria-label': 'Upload'}),
        }


class SignupForm(forms.Form):
    user_id = forms.IntegerField(required=True)
    name = forms.CharField(max_length=100, label='Full Name')
    email = forms.EmailField(max_length=100, label='Email', required=False)
    password = forms.CharField(widget=forms.PasswordInput(), max_length=128, label='Password')
    user_type = forms.ChoiceField(choices=(('ST', 'Student'), ('FA', 'Faculty')))
    membership = forms.ChoiceField(choices=(('b', 'Bronze'),), initial='b', required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), empty_label=None)

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'code',
            'name',
            'faculty',
            'price',
            'description',
            'membership_level',
            'department',
            'studentKey',
            'facultyKey',
        ]

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=100)