import datetime
from django.shortcuts import redirect, render, reverse
from django.contrib import messages
from .models import Student, Course, Announcement, Assignment, Submission, Material, Faculty, Department, Payment, Membership
from django.template.defaulttags import register
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from .forms import AnnouncementForm, AssignmentForm, MaterialForm
from django import forms
from django.core import validators
from django.conf import settings
import stripe
from django import forms
from .forms import SignupForm, CourseForm, ForgotPasswordForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.urls import reverse
from django.contrib.auth.forms import SetPasswordForm
from django.utils.http import urlsafe_base64_decode
from django.views import View
# from django.utils.encoding import force_bytes

class MyTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}"

my_token_generator = MyTokenGenerator()
class LoginForm(forms.Form):
    id = forms.CharField(label='ID', max_length=10, validators=[
                         validators.RegexValidator(r'^\d+$', 'Please enter a valid number.')])
    password = forms.CharField(widget=forms.PasswordInput)


def is_student_authorised(request, code):
    course = Course.objects.get(code=code)
    if request.session.get('student_id') and course in Student.objects.get(student_id=request.session['student_id']).course.all():
        return True
    else:
        return False


def is_faculty_authorised(request, code):
    if request.session.get('faculty_id') and code in Course.objects.filter(faculty_id=request.session['faculty_id']).values_list('code', flat=True):
        return True
    else:
        return False

class LoginView(View):
    template_name = 'login_page.html'
    error_messages = []

    def get(self, request):
        form = LoginForm()

        if 'user_type' in request.COOKIES:
            user_type = request.COOKIES['user_type']
            if user_type == 'student':
                return redirect('myCourses')
            elif user_type == 'faculty':
                return redirect('facultyCourses')

        context = {'form': form, 'error_messages': self.error_messages}
        return render(request, self.template_name, context)

    def post(self, request):
        form = LoginForm(request.POST)

        if form.is_valid():
            id = form.cleaned_data['id']
            password = form.cleaned_data['password']

            if Student.objects.filter(student_id=id, password=password).exists():
                response = redirect('myCourses')
                response.set_cookie('user_type', 'student')
                response.set_cookie('user_id', id)
                return response
            elif Faculty.objects.filter(faculty_id=id, password=password).exists():
                response = redirect('facultyCourses')
                response.set_cookie('user_type', 'faculty')
                response.set_cookie('user_id', id)
                return response
            else:
                self.error_messages.append('Invalid login credentials.')
        else:
            self.error_messages.append('Invalid form data.')

        form = LoginForm()  # Reset the form after an unsuccessful login
        context = {'form': form, 'error_messages': self.error_messages}
        return render(request, self.template_name, context)

# Custom Login page for both student and faculty
def std_login(request):
    error_messages = []

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            id = form.cleaned_data['id']
            password = form.cleaned_data['password']

            if Student.objects.filter(student_id=id, password=password).exists():
                request.session['student_id'] = id
                response = redirect('myCourses')
                response.set_cookie('user_type', 'student')
                response.set_cookie('user_id', id)
                return response
                # return redirect('myCourses')
            elif Faculty.objects.filter(faculty_id=id, password=password).exists():
                request.session['faculty_id'] = id
                response = redirect('facultyCourses')
                response.set_cookie('user_type', 'faculty')
                response.set_cookie('user_id', id)
                return response
                # return redirect('facultyCourses')
            else:
                error_messages.append('Invalid login credentials.')
        else:
            error_messages.append('Invalid form data.')
    else:
        form = LoginForm()

    if 'student_id' in request.session:
        return redirect('/my/')
    elif 'faculty_id' in request.session:
        return redirect('/facultyCourses/')

    # if 'user_type' in request.COOKIES:
    #     user_type = request.COOKIES['user_type']
    #     if user_type == 'student':
    #         return redirect('/my/')
    #     elif user_type == 'faculty':
    #         return redirect('/facultyCourses/')

    context = {'form': form, 'error_messages': error_messages}
    return render(request, 'login_page.html', context)

# Clears the session on logout


def std_logout(request):
    request.session.flush()
    return redirect('std_login')


# Display all courses (student view)
def myCourses(request):
    try:
        if request.session.get('student_id'):
            student = Student.objects.get(
                student_id=request.session['student_id'])
            courses = student.course.all()
            faculty = student.course.all().values_list('faculty_id', flat=True)

            context = {
                'courses': courses,
                'student': student,
                'faculty': faculty
            }

            return render(request, 'main/myCourses.html', context)
        else:
            return redirect('std_login')
    except:
        return render(request, 'error.html')

class MyCoursesView(View):
    template_name = 'main/myCourses.html'

    def get(self, request, *args, **kwargs):
        try:
            if request.session.get('student_id'):
                student = Student.objects.get(student_id=request.session['student_id'])
                courses = student.course.all()
                faculty = student.course.all().values_list('faculty_id', flat=True)

                context = {
                    'courses': courses,
                    'student': student,
                    'faculty': faculty
                }

                return render(request, self.template_name, context)
            else:
                return redirect('std_login')
        except:
            return render(request, 'error.html')
# Display all courses (faculty view)
def facultyCourses(request):
    try:
        if request.session['faculty_id']:
            faculty = Faculty.objects.get(
                faculty_id=request.session['faculty_id'])
            courses = Course.objects.filter(
                faculty_id=request.session['faculty_id'])
            # Student count of each course to show on the faculty page
            studentCount = Course.objects.all().annotate(student_count=Count('students'))

            studentCountDict = {}

            for course in studentCount:
                studentCountDict[course.code] = course.student_count

            @register.filter
            def get_item(dictionary, course_code):
                return dictionary.get(course_code)

            context = {
                'courses': courses,
                'faculty': faculty,
                'studentCount': studentCountDict
            }

            return render(request, 'main/facultyCourses.html', context)

        else:
            return redirect('std_login')
    except:

        return redirect('std_login')


# Particular course page (student view)
def course_page(request, code):
    try:
        course = Course.objects.get(code=code)
        if is_student_authorised(request, code):
            try:
                announcements = Announcement.objects.filter(course_code=course)
                assignments = Assignment.objects.filter(
                    course_code=course.code)
                materials = Material.objects.filter(course_code=course.code)

            except:
                announcements = None
                assignments = None
                materials = None

            context = {
                'course': course,
                'announcements': announcements,
                'assignments': assignments[:3],
                'materials': materials,
                'student': Student.objects.get(student_id=request.session['student_id'])
            }

            return render(request, 'main/course.html', context)

        else:
            return redirect('std_login')
    except:
        return render(request, 'error.html')


# Particular course page (faculty view)
def course_page_faculty(request, code):
    course = Course.objects.get(code=code)
    if request.session.get('faculty_id'):
        try:
            announcements = Announcement.objects.filter(course_code=course)
            assignments = Assignment.objects.filter(
                course_code=course.code)
            materials = Material.objects.filter(course_code=course.code)
            studentCount = Student.objects.filter(course=course).count()

        except:
            announcements = None
            assignments = None
            materials = None

        context = {
            'course': course,
            'announcements': announcements,
            'assignments': assignments[:3],
            'materials': materials,
            'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']),
            'studentCount': studentCount
        }

        return render(request, 'main/faculty_course.html', context)
    else:
        return redirect('std_login')


def error(request):
    return render(request, 'error.html')


# Display user profile(student & faculty)
def profile(request, id):
    try:
        if request.session['student_id'] == id:
            student = Student.objects.get(student_id=id)
            return render(request, 'main/profile.html', {'student': student})
        else:
            return redirect('std_login')
    except:
        try:
            if request.session['faculty_id'] == id:
                faculty = Faculty.objects.get(faculty_id=id)
                return render(request, 'main/faculty_profile.html', {'faculty': faculty})
            else:
                return redirect('std_login')
        except:
            return render(request, 'error.html')


def addAnnouncement(request, code):
    if is_faculty_authorised(request, code):
        if request.method == 'POST':
            form = AnnouncementForm(request.POST)
            form.instance.course_code = Course.objects.get(code=code)
            if form.is_valid():
                form.save()
                messages.success(
                    request, 'Announcement added successfully.')
                return redirect('/faculty/' + str(code))
        else:
            form = AnnouncementForm()
        return render(request, 'main/announcement.html', {'course': Course.objects.get(code=code), 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']), 'form': form})
    else:
        return redirect('std_login')


def deleteAnnouncement(request, code, id):
    if is_faculty_authorised(request, code):
        try:
            announcement = Announcement.objects.get(course_code=code, id=id)
            announcement.delete()
            messages.warning(request, 'Announcement deleted successfully.')
            return redirect('/faculty/' + str(code))
        except:
            return redirect('/faculty/' + str(code))
    else:
        return redirect('std_login')


def editAnnouncement(request, code, id):
    if is_faculty_authorised(request, code):
        announcement = Announcement.objects.get(course_code_id=code, id=id)
        form = AnnouncementForm(instance=announcement)
        context = {
            'announcement': announcement,
            'course': Course.objects.get(code=code),
            'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']),
            'form': form
        }
        return render(request, 'main/update-announcement.html', context)
    else:
        return redirect('std_login')


def updateAnnouncement(request, code, id):
    if is_faculty_authorised(request, code):
        try:
            announcement = Announcement.objects.get(course_code_id=code, id=id)
            form = AnnouncementForm(request.POST, instance=announcement)
            if form.is_valid():
                form.save()
                messages.info(request, 'Announcement updated successfully.')
                return redirect('/faculty/' + str(code))
        except:
            return redirect('/faculty/' + str(code))

    else:
        return redirect('std_login')


def addAssignment(request, code):
    if is_faculty_authorised(request, code):
        if request.method == 'POST':
            form = AssignmentForm(request.POST, request.FILES)
            form.instance.course_code = Course.objects.get(code=code)
            if form.is_valid():
                form.save()
                messages.success(request, 'Assignment added successfully.')
                return redirect('/faculty/' + str(code))
        else:
            form = AssignmentForm()
        return render(request, 'main/assignment.html', {'course': Course.objects.get(code=code), 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']), 'form': form})
    else:
        return redirect('std_login')


def assignmentPage(request, code, id):
    course = Course.objects.get(code=code)
    if is_student_authorised(request, code):
        assignment = Assignment.objects.get(course_code=course.code, id=id)
        try:

            submission = Submission.objects.get(assignment=assignment, student=Student.objects.get(
                student_id=request.session['student_id']))

            context = {
                'assignment': assignment,
                'course': course,
                'submission': submission,
                'time': datetime.datetime.now(),
                'student': Student.objects.get(student_id=request.session['student_id']),
                'courses': Student.objects.get(student_id=request.session['student_id']).course.all()
            }

            return render(request, 'main/assignment-portal.html', context)

        except:
            submission = None

        context = {
            'assignment': assignment,
            'course': course,
            'submission': submission,
            'time': datetime.datetime.now(),
            'student': Student.objects.get(student_id=request.session['student_id']),
            'courses': Student.objects.get(student_id=request.session['student_id']).course.all()
        }

        return render(request, 'main/assignment-portal.html', context)
    else:

        return redirect('std_login')


def allAssignments(request, code):
    if is_faculty_authorised(request, code):
        course = Course.objects.get(code=code)
        assignments = Assignment.objects.filter(course_code=course)
        studentCount = Student.objects.filter(course=course).count()

        context = {
            'assignments': assignments,
            'course': course,
            'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']),
            'studentCount': studentCount

        }
        return render(request, 'main/all-assignments.html', context)
    else:
        return redirect('std_login')


def allAssignmentsSTD(request, code):
    if is_student_authorised(request, code):
        course = Course.objects.get(code=code)
        assignments = Assignment.objects.filter(course_code=course)
        context = {
            'assignments': assignments,
            'course': course,
            'student': Student.objects.get(student_id=request.session['student_id']),

        }
        return render(request, 'main/all-assignments-std.html', context)
    else:
        return redirect('std_login')


def addSubmission(request, code, id):
    try:
        course = Course.objects.get(code=code)
        if is_student_authorised(request, code):
            # check if assignment is open
            assignment = Assignment.objects.get(course_code=course.code, id=id)
            if assignment.deadline < datetime.datetime.now():

                return redirect('/assignment/' + str(code) + '/' + str(id))

            if request.method == 'POST' and request.FILES['file']:
                assignment = Assignment.objects.get(
                    course_code=course.code, id=id)
                submission = Submission(assignment=assignment, student=Student.objects.get(
                    student_id=request.session['student_id']), file=request.FILES['file'],)
                submission.status = 'Submitted'
                submission.save()
                return HttpResponseRedirect(request.path_info)
            else:
                assignment = Assignment.objects.get(
                    course_code=course.code, id=id)
                submission = Submission.objects.get(assignment=assignment, student=Student.objects.get(
                    student_id=request.session['student_id']))
                context = {
                    'assignment': assignment,
                    'course': course,
                    'submission': submission,
                    'time': datetime.datetime.now(),
                    'student': Student.objects.get(student_id=request.session['student_id']),
                    'courses': Student.objects.get(student_id=request.session['student_id']).course.all()
                }

                return render(request, 'main/assignment-portal.html', context)
        else:
            return redirect('std_login')
    except:
        return HttpResponseRedirect(request.path_info)


def viewSubmission(request, code, id):
    course = Course.objects.get(code=code)
    if is_faculty_authorised(request, code):
        try:
            assignment = Assignment.objects.get(course_code_id=code, id=id)
            submissions = Submission.objects.filter(
                assignment_id=assignment.id)

            context = {
                'course': course,
                'submissions': submissions,
                'assignment': assignment,
                'totalStudents': len(Student.objects.filter(course=course)),
                'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']),
                'courses': Course.objects.filter(faculty_id=request.session['faculty_id'])
            }

            return render(request, 'main/assignment-view.html', context)

        except:
            return redirect('/faculty/' + str(code))
    else:
        return redirect('std_login')


def gradeSubmission(request, code, id, sub_id):
    try:
        course = Course.objects.get(code=code)
        if is_faculty_authorised(request, code):
            if request.method == 'POST':
                assignment = Assignment.objects.get(course_code_id=code, id=id)
                submissions = Submission.objects.filter(
                    assignment_id=assignment.id)
                submission = Submission.objects.get(
                    assignment_id=id, id=sub_id)
                submission.marks = request.POST['marks']
                if request.POST['marks'] == 0:
                    submission.marks = 0
                submission.save()
                return HttpResponseRedirect(request.path_info)
            else:
                assignment = Assignment.objects.get(course_code_id=code, id=id)
                submissions = Submission.objects.filter(
                    assignment_id=assignment.id)
                submission = Submission.objects.get(
                    assignment_id=id, id=sub_id)

                context = {
                    'course': course,
                    'submissions': submissions,
                    'assignment': assignment,
                    'totalStudents': len(Student.objects.filter(course=course)),
                    'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']),
                    'courses': Course.objects.filter(faculty_id=request.session['faculty_id'])
                }

                return render(request, 'main/assignment-view.html', context)

        else:
            return redirect('std_login')
    except:
        return redirect('/error/')


def addCourseMaterial(request, code):
    if is_faculty_authorised(request, code):
        if request.method == 'POST':
            form = MaterialForm(request.POST, request.FILES)
            form.instance.course_code = Course.objects.get(code=code)
            if form.is_valid():
                form.save()
                messages.success(request, 'New course material added')
                return redirect('/faculty/' + str(code))
            else:
                return render(request, 'main/course-material.html', {'course': Course.objects.get(code=code), 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']), 'form': form})
        else:
            form = MaterialForm()
            return render(request, 'main/course-material.html', {'course': Course.objects.get(code=code), 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id']), 'form': form})
    else:
        return redirect('std_login')


def deleteCourseMaterial(request, code, id):
    if is_faculty_authorised(request, code):
        course = Course.objects.get(code=code)
        course_material = Material.objects.get(course_code=course, id=id)
        course_material.delete()
        messages.warning(request, 'Course material deleted')
        return redirect('/faculty/' + str(code))
    else:
        return redirect('std_login')


def courses(request):
    if request.session.get('student_id') or request.session.get('faculty_id'):

        courses = Course.objects.all()
        # courses = Course.objects.filter(membership_level='g')
        if request.session.get('student_id'):
            student = Student.objects.get(
                student_id=request.session['student_id'])
            if student.membership == 'g':
                courses = Course.objects.all()
            elif student.membership == 's':
                courses = Course.objects.filter(membership_level__in = ['b', 's'])
            else:
                courses = Course.objects.filter(membership_level='b')
            # courses = Course.objects.filter(membership_level=student.membership)
        else:
            student = None
        if request.session.get('faculty_id'):
            faculty = Faculty.objects.get(
                faculty_id=request.session['faculty_id'])
        else:
            faculty = None

        enrolled = student.course.all() if student else None
        accessed = Course.objects.filter(
            faculty_id=faculty.faculty_id) if faculty else None

        context = {
            'faculty': faculty,
            'courses': courses,
            'student': student,
            'enrolled': enrolled,
            'accessed': accessed
        }

        return render(request, 'main/all-courses.html', context)

    else:
        return redirect('std_login')

def departments(request):
    if request.session.get('student_id') or request.session.get('faculty_id'):
        departments = Department.objects.all()
        if request.session.get('student_id'):
            student = Student.objects.get(
                student_id=request.session['student_id'])
        else:
            student = None
        if request.session.get('faculty_id'):
            faculty = Faculty.objects.get(
                faculty_id=request.session['faculty_id'])
        else:
            faculty = None
        context = {
            'faculty': faculty,
            'student': student,
            'deps': departments
        }

        return render(request, 'main/departments.html', context)

    else:
        return redirect('std_login')


def access(request, code):
    if request.session.get('student_id'):
        course = Course.objects.get(code=code)
        student = Student.objects.get(student_id=request.session['student_id'])
        if request.method == 'POST':
            if (request.POST['key']) == str(course.studentKey):
                # print("correct key")
                # print(course)
                student.course.add(course)
                student.save()

                # print(student.course.all())
                return redirect('/my/')
            else:
                messages.error(request, 'Invalid key')
                return HttpResponseRedirect(request.path_info)
        else:
            # Send an email to the user with the access code
            access_code = course.studentKey
            subject = 'Access Code for Course'
            template_name = 'main/access_code_email.html'
            current_site = get_current_site(request)

            # Render the email content using the template
            email_content = render_to_string(template_name, {
                'access_code': access_code,
                'domain': current_site.domain,
                'user': student,
                'course': course,
            })

            # Create an EmailMessage object
            email = EmailMessage(
                subject=subject,
                body=email_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[student.email],  # Replace with the actual recipient's email address
            )

            # Send the email
            email.send()
            return render(request, 'main/access.html', {'course': course, 'student': student})

    else:
        return redirect('std_login')


def search(request):
    if request.session.get('student_id') or request.session.get('faculty_id'):
        if request.method == 'GET' and request.GET['q']:
            q = request.GET['q']
            courses = Course.objects.filter(Q(code__icontains=q) | Q(
                name__icontains=q) | Q(faculty__name__icontains=q))

            if request.session.get('student_id'):
                student = Student.objects.get(
                    student_id=request.session['student_id'])
            else:
                student = None
            if request.session.get('faculty_id'):
                faculty = Faculty.objects.get(
                    faculty_id=request.session['faculty_id'])
            else:
                faculty = None
            enrolled = student.course.all() if student else None
            accessed = Course.objects.filter(
                faculty_id=faculty.faculty_id) if faculty else None

            context = {
                'courses': courses,
                'faculty': faculty,
                'student': student,
                'enrolled': enrolled,
                'accessed': accessed,
                'q': q
            }
            return render(request, 'main/search.html', context)
        else:
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    else:
        return redirect('std_login')


def changePasswordPrompt(request):
    if request.session.get('student_id'):
        student = Student.objects.get(student_id=request.session['student_id'])
        return render(request, 'main/changePassword.html', {'student': student})
    elif request.session.get('faculty_id'):
        faculty = Faculty.objects.get(faculty_id=request.session['faculty_id'])
        return render(request, 'main/changePasswordFaculty.html', {'faculty': faculty})
    else:
        return redirect('std_login')


def changePhotoPrompt(request):
    if request.session.get('student_id'):
        student = Student.objects.get(student_id=request.session['student_id'])
        return render(request, 'main/changePhoto.html', {'student': student})
    elif request.session.get('faculty_id'):
        faculty = Faculty.objects.get(faculty_id=request.session['faculty_id'])
        return render(request, 'main/changePhotoFaculty.html', {'faculty': faculty})
    else:
        return redirect('std_login')


def changePassword(request):
    if request.session.get('student_id'):
        student = Student.objects.get(
            student_id=request.session['student_id'])
        if request.method == 'POST':
            if student.password == request.POST['oldPassword']:
                # New and confirm password check is done in the client side
                student.password = request.POST['newPassword']
                student.save()
                messages.success(request, 'Password was changed successfully')
                return redirect('/profile/' + str(student.student_id))
            else:
                messages.error(
                    request, 'Password is incorrect. Please try again')
                return redirect('/changePassword/')
        else:
            return render(request, 'main/changePassword.html', {'student': student})
    else:
        return redirect('std_login')


def changePasswordFaculty(request):
    if request.session.get('faculty_id'):
        faculty = Faculty.objects.get(
            faculty_id=request.session['faculty_id'])
        if request.method == 'POST':
            if faculty.password == request.POST['oldPassword']:
                # New and confirm password check is done in the client side
                faculty.password = request.POST['newPassword']
                faculty.save()
                messages.success(request, 'Password was changed successfully')
                return redirect('/facultyProfile/' + str(faculty.faculty_id))
            else:
                print('error')
                messages.error(
                    request, 'Password is incorrect. Please try again')
                return redirect('/changePasswordFaculty/')
        else:
            print(faculty)
            return render(request, 'main/changePasswordFaculty.html', {'faculty': faculty})
    else:
        return redirect('std_login')


def changePhoto(request):
    if request.session.get('student_id'):
        student = Student.objects.get(
            student_id=request.session['student_id'])
        if request.method == 'POST':
            if request.FILES['photo']:
                student.photo = request.FILES['photo']
                student.save()
                messages.success(request, 'Photo was changed successfully')
                return redirect('/profile/' + str(student.student_id))
            else:
                messages.error(
                    request, 'Please select a photo')
                return redirect('/changePhoto/')
        else:
            return render(request, 'main/changePhoto.html', {'student': student})
    else:
        return redirect('std_login')


def changePhotoFaculty(request):
    if request.session.get('faculty_id'):
        faculty = Faculty.objects.get(
            faculty_id=request.session['faculty_id'])
        if request.method == 'POST':
            if request.FILES['photo']:
                faculty.photo = request.FILES['photo']
                faculty.save()
                messages.success(request, 'Photo was changed successfully')
                return redirect('/facultyProfile/' + str(faculty.faculty_id))
            else:
                messages.error(
                    request, 'Please select a photo')
                return redirect('/changePhotoFaculty/')
        else:
            return render(request, 'main/changePhotoFaculty.html', {'faculty': faculty})
    else:
        return redirect('std_login')


def guestStudent(request):
    request.session.flush()
    try:
        student = Student.objects.get(name='Guest Student')
        request.session['student_id'] = str(student.student_id)
        return redirect('myCourses')
    except:
        return redirect('std_login')


def guestFaculty(request):
    request.session.flush()
    try:
        faculty = Faculty.objects.get(name='Guest Faculty')
        request.session['faculty_id'] = str(faculty.faculty_id)
        return redirect('facultyCourses')
    except:
        return redirect('std_login')


def payment(request, course_code):
    print(course_code)
    if request.session.get('student_id'):
        student = Student.objects.get(
            student_id=request.session['student_id'])
    else:
        student = None
    if request.session.get('faculty_id'):
        faculty = Faculty.objects.get(
            faculty_id=request.session['faculty_id'])
    else:
        faculty = None
    if request.method in ['GET','POST']:
        # course_code = request.POST['code']
        course = Course.objects.get(code=course_code)
        amount = course.price
        description = course.description

        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe_pk = settings.STRIPE_PUBLIC_KEY
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount*100),
                currency='usd',
            )
            payment = Payment.objects.create(course=course, amount=amount, description=description)
            payment.save()
            payment_success = True  # Set payment_success to True if payment is successful
        except stripe.error.CardError as e:
            error_message = e.error.message
            return render(request, 'main/payment_error.html', {'error_message': error_message})

        access_code = course.studentKey

        access_code = course.studentKey
        subject = 'Access Code for Course'
        template_name = 'main/access_code_email.html'

        # Render the email content using the template
        email_content = render_to_string(template_name, {'access_code': access_code})
        student_email = 'jksingh.js7@gmail.com'
        # Create an EmailMessage object
        email = EmailMessage(
            subject=subject,
            body=email_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[student_email],# Replace with the actual recipient's email address
            connection=None
        )

        # # Configure the email backend with Elastic Email SMTP settings
        # email.connection = {
        #     'host': 'smtp.elasticemail.com',
        #     'port': 2525,
        #     'username': settings.EMAIL_HOST_USER,
        #     'password': settings.EMAIL_HOST_PASSWORD,
        #     'use_tls': True,
        #     'fail_silently': False,
        # }

        # Send the email
        # email.send()


        return render(request, 'main/payment.html', {
            'stripe_public_key': stripe_pk,
            'client_secret': intent.client_secret,
            'course': course,
            'payment_success': payment_success,
            'student': student,
            'faculty': faculty,
        })

    return render(request, 'main/payment.html')



def membership(request):
    # Fetch membership details from the Membership model
    memberships = Membership.objects.all()
    if request.session.get('student_id'):
        student = Student.objects.get(
            student_id=request.session['student_id'])
    else:
        student = None
    if request.session.get('faculty_id'):
        faculty = Faculty.objects.get(
            faculty_id=request.session['faculty_id'])
    else:
        faculty = None
    context = {
        'memberships': memberships,
        'student': student,
        'faculty': faculty,
    }

    return render(request, 'main/membership_new.html', context)

def membership_payment(request, selected_membership_pk):
    selected_membership = Membership.objects.get(pk=selected_membership_pk)
    if request.session.get('student_id'):
        student = Student.objects.get(
            student_id=request.session['student_id'])
    else:
        student = None
    if request.session.get('faculty_id'):
        faculty = Faculty.objects.get(
            faculty_id=request.session['faculty_id'])
    else:
        faculty = None
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Initialize payment_success to False
    payment_success = False

    if request.method == 'GET':
        # Create a PaymentIntent and get the client_secret for the payment form
        intent = stripe.PaymentIntent.create(
            amount=int(selected_membership.price * 100),  # Amount in cents
            currency='usd',
        )
        client_secret = intent.client_secret

    # elif request.method == 'POST':
    #     # Get the payment details from the form
    #     stripe.api_key = settings.STRIPE_SECRET_KEY
    #
    #     # Assume you have received the payment details from the form
    #     # and have the necessary payment processing code here.
    #     # For example, if you have received a successful payment, set payment_success to True
    #
    #     # Sample code for payment processing using Stripe
    #     try:
    #         # Replace the following line with your actual payment processing code
    #         # For example, if payment is successful, set payment_success to True
    #         # payment_success = True
    #
    #         # Since this is just a sample, we'll simulate a successful payment here
    #         payment_success = True
    #
    #     except stripe.error.CardError as e:
    #         error_message = e.error.message
    #         return render(request, 'main/payment_error.html', {'error_message': error_message})
    #     except Exception as e:
    #         error_message = str(e)
    #         return render(request, 'main/payment_error.html', {'error_message': error_message})
    #
    #     if payment_success:
    #         # Update the student's membership
    #         if selected_membership.name == 'Gold':
    #             student.membership = 'g'
    #         elif selected_membership.name == 'Silver':
    #             student.membership = 's'
    #         else:
    #             student.membership = 'b'
    #         student.save()
    #
    #         # Redirect to a success page after successful payment
    #         return redirect('membership_payment_success')

    context = {
        'selected_membership': selected_membership,
        'student': student,
        'faculty': faculty,
        'client_secret': client_secret if request.method == 'GET' else '',  # Pass the client_secret to the template
        'payment_success': payment_success,  # Pass the payment_success flag to the template
    }
    return render(request, 'main/membership_payment.html', context)

def send_membership_email(request, user, selected_membership):
    current_site = get_current_site(request)
    subject = 'Membership Purchase Confirmation'
    protocol = settings.SITE_PROTOCOL

    # Render the email content using the template
    email_content = render_to_string('main/membership_confirmation_email.html', {
        'user': user,
        'membership': selected_membership,
        'protocol': protocol,
        'domain': current_site.domain,
    })

    # Create an EmailMessage object
    email = EmailMessage(
        subject=subject,
        body=email_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],  # Replace with the actual recipient's email address
    )

    # Send the email
    email.send()
def access_courses(request, code):
    selected_membership = Membership.objects.get(pk=code)
    std_id = request.session.get('student_id')
    student = Student.objects.get(student_id=std_id)

    if selected_membership.name == 'Gold':
        student.membership = 'g'
    elif selected_membership.name == 'Silver':
        student.membership = 's'
    else:
        student.membership = 'b'
    student.save()

    # Send the membership purchase email to the user
    send_membership_email(request, student, selected_membership)
    return redirect('courses')

def signup(request):
    if request.method == 'POST':
        print("I AM IN POST")
        form = SignupForm(request.POST)

        if form.is_valid():
            print("Form is Valid")
            user_type = request.POST.get('user_type')
            print(user_type)
            if user_type == 'ST':  # Student
                student = Student(
                    student_id=form.cleaned_data['user_id'],
                    name=form.cleaned_data['name'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    membership=form.cleaned_data['membership'],
                    role="Student",
                    department=form.cleaned_data['department']
                )
                print(student)
                student.save()
            elif user_type == 'FA':  # Faculty
                faculty = Faculty(
                    faculty_id=form.cleaned_data['user_id'],
                    name=form.cleaned_data['name'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    role="Faculty",
                    department=form.cleaned_data['department']
                )
                print(faculty)
                faculty.save()

            # Redirect to the login page after successful signup
            return redirect('std_login')
        else:
            print("NOT VALID")
            print(form.errors)
    else:
        print("GET")
        form = SignupForm()

    return render(request, 'signup.html', {'form': form})


def add_course(request):
    f_id = request.session.get('faculty_id')
    faculty = Faculty.objects.get(faculty_id=f_id)
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            # Save the new course
            course = form.save(commit=False)
            # Assuming you have the faculty object available in the current session
            # course.faculty = request.session.get('faculty', None)
            course.save()
            return redirect('courses')
    else:
        form = CourseForm()
    return render(request, 'main/add_course.html', {'form': form, 'faculty': faculty})

class AddCourseView(View):
    template_name = 'main/add_course.html'

    def get(self, request, *args, **kwargs):
        f_id = request.session.get('faculty_id')
        faculty = Faculty.objects.get(faculty_id=f_id)
        form = CourseForm()
        return render(request, self.template_name, {'form': form, 'faculty': faculty})

    def post(self, request, *args, **kwargs):
        f_id = request.session.get('faculty_id')
        faculty = Faculty.objects.get(faculty_id=f_id)
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.faculty = faculty
            course.save()
            return redirect('courses')
        return render(request, self.template_name, {'form': form, 'faculty': faculty})

def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = Student.objects.get(email=email)
                # print(user.name)
                current_site = get_current_site(request)
                subject = 'Password Reset Request'
                protocol = settings.SITE_PROTOCOL
                # path = reverse('password_reset_confirm', kwargs={'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                #                                                  'token': my_token_generator.make_token(user)})
                # reset_link = f'{protocol}://{current_site.domain}{path}'
                message = render_to_string('main/password_reset_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': my_token_generator.make_token(user),
                    'protocol': protocol,
                    # 'token': default_token_generator.make_token(user),
                })
                send_mail(subject, message, 'jazzy199907@gmail.com', [email])
                messages.success(request, 'Password reset email has been sent. Please check your email.')
                return redirect('std_login')
            except Student.DoesNotExist:
                messages.error(request, 'User with this email address does not exist.')
    return render(request, 'main/forgot_password.html', {'form': form})

def password_reset_confirm(request, uidb64, token):
    print("I am here")
    form = SetPasswordForm(user=None)  # Initialize the form without a user
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Student.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Student.DoesNotExist):
        user = None

    if user is not None and my_token_generator.check_token(user, token):
        if request.method == 'POST':
            print("POST request")

            if user.password == request.POST['oldPassword']:
                print("password match")
                # New and confirm password check is done in the client side
                user.password = request.POST['newPassword']
                user.save()
                messages.success(request, 'Password was changed successfully')
                return redirect('/profile/' + str(user.student_id))
            else:
                messages.error(
                    request, 'Password is incorrect. Please try again')
                return redirect('/changePassword/')
        else:
            return render(request, 'main/password_reset_confirm.html', {'user': user, 'password': True})

    return render(request, 'main/password_reset_confirm.html', {'form': form, 'user': user, 'token': token, 'password': True})

def password_reset_view(request):
    if request.method == 'POST':
        print("POST request")
        user = Student.objects.get(pk=request.POST['student_id'])
        if user.password == request.POST['oldPassword']:
            print("password match")
            # New and confirm password check is done in the client side
            user.password = request.POST['newPassword']
            user.save()
            # messages.success(request, 'Password was changed successfully')
            return redirect('password_reset_complete')
        else:
            messages.error(
                request, 'Password is incorrect. Please try again')
            return redirect('password_error')
    else:
        return redirect('std_login')

    #
    # else:
    #     return redirect('std_login')