import re
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, HttpResponseRedirect
from django.views import generic
from django.views.generic.dates import DayArchiveView
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, F, Value, Q
from django.db.models.functions import Concat
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from datetime import date, time, timedelta, datetime
import json
import csv
from io import TextIOWrapper
import xlrd
from pathlib import Path
from rapidfuzz import process, fuzz

class GoogleRawLoginCredentials:
    def __init__(self, client_id = "", client_secret = "", project_id = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.project_id = project_id

def google_login_get_credentials():
        client_id = settings.GOOGLE_OAUTH_CLIENT_ID
        client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET
        project_id = settings.GOOGLE_OAUTH_PROJECT_ID

        if not client_id:
            raise ImproperlyConfigured("GOOGLE_OAUTH_CLIENT_ID is missing in env.")

        if not client_secret:
            raise ImproperlyConfigured("GOOGLE_OAUTH_CLIENT_SECRET is missing in env.")

        if not project_id:
            raise ImproperlyConfigured("GOOGLE_PROJECT_CLIENT_ID is missing in env.")

        credentials = GoogleRawLoginCredentials(client_id, client_secret, project_id)
        return credentials

# Create your views here.

from .models import AcademicYear, Course, Enrolment, Lesson, NonSchoolDay, Student, AttendanceRecord, Period, Teacher, Section, WeeklySchedule, AttendanceStatus
from .forms import AcademicYearForm
from .parsecourse import Parser


def weekdayrange(from_date: date, to_date: date, iso_weekday, filter_fn=None):
    """
    Iterates over all days with given iso_weekday,
    in the range [from_date, to_date) for which filter_fn returns True.
    """
    days_ahead = (iso_weekday - from_date.isoweekday()) % 7
    current = from_date + timedelta(days=days_ahead)
    while current < to_date:
        if filter_fn is None or filter_fn(current):
            yield current
        current += timedelta(days=7)

def is_school_day(d: date):
    ay = AcademicYear.objects.all()[0]
    return (d >= ay.start_date) and (d <= ay.end_date) and (NonSchoolDay.objects.filter(date=d).count() == 0)

def is_future_school_day(d: date):
    return is_school_day(d) and d > date.today()

def is_past_school_day(d: date):
    return is_school_day(d) and d < date.today()

def do_generate_attendance_records(lesson: Lesson):
    """Generate attendance records for given lesson."""
    att_record_num = 0
    enrolment_set = Enrolment.objects.filter(course=lesson.course)
    for enrolment in enrolment_set.iterator():
        ar = AttendanceRecord(
            student=enrolment.student,
            lesson=lesson,
            status=AttendanceStatus.UNREGISTERED
        )
        ar.save()
        att_record_num = att_record_num + 1
    return att_record_num

def do_generate_all_attendance_records():
    """Generate an attendance record for every student for every lesson he's enrolled in."""
    lesson_set = Lesson.objects.all()
    att_record_num = 0
    for lesson in lesson_set.iterator():
        att_records_added = do_generate_attendance_records(lesson)
        att_record_num = att_record_num + att_records_added
    return att_record_num

# TODO Eliminate redundancy in the weekdayrange call.
# The filter only takes into account the academic year, but the start and end are already
# limiting that. At the same time, the filter only allows for future dates,
# but we could set from_date = date.today() to achieve the same result.
def do_generate_lessons_and_att_records(ws: WeeklySchedule, from_date: date, to_date: date):
    """Generate lessons corresponding to a weekly schedule."""
    lesson_num = 0
    teacher = ws.course.teacher
    for d in weekdayrange(from_date, to_date, ws.iso_weekday, filter_fn=is_future_school_day):
        if d < to_date:
            lesson = Lesson(
                course=ws.course,
                teacher=teacher,
                period=ws.period,
                date=d,
                start_datetime=timezone.datetime(d.year, d.month, d.day, ws.period.start_time.hour, ws.period.start_time.minute)
            )
            lesson.save()
            do_generate_attendance_records(lesson)
            lesson_num = lesson_num + 1
    return lesson_num

def do_generate_all_lessons():
    course_start = AcademicYear.objects.all()[0].start_date
    course_end = AcademicYear.objects.all()[0].end_date + timedelta(days=1)
    weekly_schedule_set = WeeklySchedule.objects.all()
    lesson_num = 0
    for ws in weekly_schedule_set.iterator():
        generated_lessons = do_generate_lessons_and_att_records(ws, course_start, course_end)
        lesson_num = lesson_num + generated_lessons
    return lesson_num

def do_delete_lessons(ws: WeeklySchedule, course_start: date, course_end: date):
    """Delete all lessons scheduled by 'ws' weekly schedule."""
    Lesson.objects.filter(course=ws.course).filter(period=ws.period).filter(date__iso_week_day=ws.iso_weekday).filter(date__gte=course_start).filter(date__lte=course_end).delete()

class WeekView(LoginRequiredMixin, generic.TemplateView):
    """Overview given week's lessons."""
    template_name = "att/week_view.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        target_date = date(int(self.kwargs["year"]), int(self.kwargs["month"]), int(self.kwargs["day"]))
        start_of_week = target_date - timedelta(days=target_date.isoweekday()-1)
        end_of_week = start_of_week + timedelta(days=6)
        previous_week = start_of_week - timedelta(days=7)
        next_week = start_of_week + timedelta(days=7)
        week_days = [start_of_week + timedelta(days=i) for i in range(5)]

        loggedin_user = self.request.user
        periods = Period.objects.all().order_by("start_time")
        lessons = Lesson.objects.filter(teacher__user=loggedin_user).filter(date__range=(start_of_week, end_of_week))
        lessons_by_day = {day: {period: None for period in periods} for day in week_days}
        for lesson in lessons:
            lessons_by_day[lesson.date][lesson.period] = lesson
        # lessons_ordered = [lessons_by_day[day] for day in week_days]
        days_and_lessons = zip(week_days, [zip(periods, [lessons_by_day[day][period] for period in periods]) for day in week_days])

        context["week_days"] = week_days
        context["periods"] = periods
        context["lessons_by_day"] = days_and_lessons
        context["start_of_week"] = start_of_week
        context["end_of_week"] = end_of_week
        context["previous_week"] = previous_week
        context["next_week"] = next_week
        context["teacher"] = get_object_or_404(Teacher, user=loggedin_user)

        return context

class CurrentWeekView(WeekView):
    """Overview current week's lessons."""

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        return WeekView.as_view()(request, year=today.year, month=today.month, day=today.day)

def unauthorised(request):
    return render(request, "att/unauthorised.html")

@login_required
def landing_view(request):
    loggedin_user = request.user
    try:
        teacher = Teacher.objects.get(user=loggedin_user)
    except:
        return render(request, "att/unauthorised.html")
    if teacher.landing_url:
        return HttpResponseRedirect(reverse(f"att:{teacher.landing_url}"))
    else:
        return HttpResponseRedirect(reverse("att:lessons-today"))

class LessonsOnDay(LoginRequiredMixin, DayArchiveView):
    """View list of lesson on 'date'"""
    template_name = "att/lessons_on_day.html"
    context_object_name = "lessons_list"
    date_field = "date"
    allow_future = True
    allow_empty = True

    def get_date(self):
        current_year = self.get_year()
        current_month = self.get_month()
        current_day = self.get_day()
        return datetime.strptime(f"{current_month} {current_day} {current_year}", "%b %d %Y").date()

    def get_queryset(self):
        loggedin_user = self.request.user
        return Lesson.objects.filter(teacher__user=loggedin_user).select_related("teacher", "period", "classroom").order_by("date", "period__start_time")[:]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_date = self.get_date()
        context["previous_day"] = current_date - timedelta(days = 1)
        context["next_day"] = current_date + timedelta(days = 1)
        periods = Period.objects.all().order_by("start_time")
        loggedin_user = self.request.user
        lessons = Lesson.objects.filter(teacher__user=loggedin_user).filter(date=current_date)
        lessons_by_period = {period: None for period in periods}
        for lesson in lessons:
            lessons_by_period[lesson.period] = lesson
        periods_and_lessons = zip(periods, [lessons_by_period[period] for period in periods])
        context["lessons_by_period"] = periods_and_lessons
        teacher = get_object_or_404(Teacher, user=loggedin_user)
        context["teacher"] = teacher
        return context

# TODO Add "back to lessons list" button
class LessonsToday(LessonsOnDay):
    """View list of today's lessons."""
    today = timezone.localdate()
    year = today.year
    month = today.strftime('%b')
    day = today.day

    def get_queryset(self):
        loggedin_user = self.request.user
        return Lesson.objects.filter(teacher__user=loggedin_user).select_related("teacher", "period", "classroom").order_by("date")

    def get_date(self):
        return timezone.localdate()

def next_lesson(current_lesson):
    teacher = current_lesson.teacher
    nl = Lesson.objects.filter(teacher=teacher).filter(start_datetime__gt=current_lesson.start_datetime).order_by("start_datetime")
    return nl.first() if nl else None

def previous_lesson(current_lesson):
    teacher = current_lesson.teacher
    pl = Lesson.objects.filter(teacher=teacher).filter(start_datetime__lt=current_lesson.start_datetime).order_by("start_datetime")
    return pl.last() if pl else None

def get_lesson_students_with_attendance_fields(lesson):
    """Return students enrolled in 'lesson' annotated with
    'attendance_status' and 'minutes_late' taken from the first
    (and only) attendance record corresponding to each student
    for that 'lesson'."""
    return AttendanceRecord.objects.filter(lesson=lesson).select_related("student")

@login_required
def lesson_detail(request, lesson_id):
    """View list of students enrolled in lesson whose id is 'lesson_id'
    annotated with attendance fields."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    attendance_records = get_lesson_students_with_attendance_fields(lesson)
    context = {
        "lesson": lesson,
        "attendance_records": attendance_records,
        "previous_lesson": previous_lesson(lesson),
        "next_lesson": next_lesson(lesson)
    }
    return render(request, "att/lesson.html", context)

@login_required
def student_on_day(request, student_id, year, month, day):
    day = date(year, month, day)
    student = Student.objects.get(pk=student_id)
    attrecords = AttendanceRecord.objects.filter(student=student, lesson__date=day).order_by("lesson__period__start_time").select_related("lesson")
    context = {
        "student": student,
        "attendance_records": attrecords,
        "day": day,
        "previous_day": day - timedelta(days=1),
        "next_day": day + timedelta(days=1),
        "today": timezone.localdate()
    }
    return render(request, "att/student_on_day.html", context)

class StudentWeekView(LoginRequiredMixin, generic.TemplateView):
    """Overview given week's lessons."""
    template_name = "att/student_week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        target_date = date(int(self.kwargs["year"]), int(self.kwargs["month"]), int(self.kwargs["day"]))
        start_of_week = target_date - timedelta(days=target_date.isoweekday()-1)
        end_of_week = start_of_week + timedelta(days=6)
        previous_week = start_of_week - timedelta(days=7)
        next_week = start_of_week + timedelta(days=7)
        week_days = [start_of_week + timedelta(days=i) for i in range(5)]

        student_id = int(self.kwargs["student_id"])
        student = get_object_or_404(Student, pk=student_id)

        loggedin_user = self.request.user
        periods = Period.objects.all().order_by("start_time")
        records = AttendanceRecord.objects.filter(student=student).filter(lesson__date__range=(start_of_week, end_of_week))
        records_by_day = {day: {period: None for period in periods} for day in week_days}
        for record in records:
            records_by_day[record.lesson.date][record.lesson.period] = record
        # lessons_ordered = [lessons_by_day[day] for day in week_days]
        days_and_records = zip(week_days, [zip(periods, [records_by_day[day][period] for period in periods]) for day in week_days])

        context["today"] = timezone.localdate()
        context["week_days"] = week_days
        context["periods"] = periods
        context["records_by_day"] = days_and_records
        context["start_of_week"] = start_of_week
        context["end_of_week"] = end_of_week
        context["previous_week"] = previous_week
        context["next_week"] = next_week
        context["student"] = student

        return context

@login_required
@require_POST
def search_student(request):
    try:
        data = json.loads(request.body)
        searchstr = data["searchstr"]
        students = Student.objects.all().order_by("last_name", "first_name")
        choices = [f"{student.last_name}, {student.first_name}" for student in students]
        result, score, index = process.extractOne(searchstr, choices, scorer=fuzz.WRatio)
        student = students[index]
        return JsonResponse({"status": "ok", "result": result, "student": student.id})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

def search_result_to_dict(search_result):
    result_dict = {
        'name': search_result[0],
        'score': search_result[1],
        'index': search_result[2]
    }
    return result_dict

@login_required
@require_POST
def do_search_students(request):
    try:
        data = json.loads(request.body)
        searchstr = data["searchstr"]
        students = Student.objects.all().order_by("last_name", "first_name")
        names = [f"{student.last_name}, {student.first_name}" for student in students]
        names_found = process.extract(searchstr, names, scorer=fuzz.WRatio, limit=10)
        search_results = [search_result_to_dict(search_result) for search_result in names_found]
        for result in search_results:
            result['student_id'] = students[result['index']].id
        return JsonResponse({"status": "ok", "search_results": search_results})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required
def select_student(request):
    today = timezone.localdate()
    context = {"today": today}
    return render(request, "att/select_student.html", context)


@login_required
def report_day(request, year, month, day):
    """Return students that have any absence or late marks on given date."""
    day = date(year, month, day)
    today = timezone.localdate()
    negative_attendance_records = AttendanceRecord.objects.filter(status__in=["absent", "late"])
    periods = Period.objects.all().order_by("start_time")
    attendance_records =[
        {
            "student": s,
            "attendance_records": [
                AttendanceRecord.objects.filter(lesson__date=day).filter(student=s).filter(lesson__period=p)
                for p in Period.objects.all().order_by("start_time")
            ]
        }
        for s in Student.objects.filter(attendancerecord__status__in=["absent", "late"], attendancerecord__lesson__date=day).distinct().order_by("last_name", "first_name")
    ]

    context = {
        "periods": periods,
        "attendance_records": attendance_records,
        "date": day,
        "today": today,
        "previous_day": day - timedelta(days=1),
        "next_day": day + timedelta(days=1)
    }

    return render(request, "att/report_day.html", context)

@login_required
def report_today(request):
    """Return students that have any absence or late marks today."""
    today = timezone.localdate()
    return HttpResponseRedirect(f"/att/report-day/{today.year}/{today.month}/{today.day}/")


@login_required
def report_student_select(request):
    return render(request, "att/report_student_select.html")


@login_required
def report_student(request, student_id):
    """Return all late or absent attendance records for given student."""
    student = get_object_or_404(Student, pk=student_id)
    records = AttendanceRecord.objects.filter(student_id=student_id, status__in=["absent","late"]).order_by("lesson__date", "lesson__period__start_time")
    context = {
        "student": student,
        "records": records
    }
    return render(request, "att/report_student.html", context)

@login_required
def report_from(request, year, month, day):
    """Return students that have any absence or late marks for given month, with summary."""
    from_day = date(year, month, day)
    today = timezone.localdate()
    late = Count("attendancerecord", filter=Q(attendancerecord__status="late"))
    absent = Count("attendancerecord", filter=Q(attendancerecord__status="absent"))
    students = Student.objects.filter(attendancerecord__lesson__date__gte=from_day, attendancerecord__status__in=["absent", "late"]).annotate(late=late).annotate(absent=absent).order_by("-absent", "-late", "last_name", "first_name")
    context = {
        "students": students,
        "from_day": from_day,
        "today": today,
        "last_7_days": today - timedelta(days=7),
        "last_30_days": today - timedelta(days=30)
    }
    return render(request, "att/report_from.html", context)

@login_required
def report_from_start(request):
    academic_year = AcademicYear.objects.all()[0]
    start = academic_year.start_date
    return HttpResponseRedirect(f"/att/report-from/{start.year}/{start.month}/{start.day}/")


# TODO Fix minutes_late field
@login_required
@require_POST
def mark_attendance(request):
    """Execute marking of attendance."""
    try:
        data = json.loads(request.body)
        student_id = data["studentId"]
        lesson_id = data["lessonId"]

        student = Student.objects.get(id=student_id)
        lesson = Lesson.objects.get(id=lesson_id)

        attendance_record = AttendanceRecord.objects.get(student=student, lesson=lesson)

        if attendance_record.status == "unregistered":
            attendance_record.status = "present"
        elif attendance_record.status == "present":
            attendance_record.status = "absent"
        elif attendance_record.status == "absent":
            attendance_record.status = "late"
            attendance_record.minutes_late = 2;
        else:
            attendance_record.status = "unregistered"
            attendance_record.minutes_late = None

        attendance_record.marked_at = timezone.now()

        attendance_record.save()

        return JsonResponse({
            "status": "ok",
            "studentId": student_id,
            "attendanceStatus": attendance_record.status,
            "minutesLate": attendance_record.minutes_late,
            "markedAt": attendance_record.marked_at
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required
@require_POST
def mark_unregistered_present(request):
    """Mark every student in lesson as present."""
    try:
        data = request.POST
        lesson_id = data["lessonId"]
        AttendanceRecord.objects.filter(lesson_id=lesson_id).filter(status=AttendanceStatus.UNREGISTERED).update(status=AttendanceStatus.PRESENT, minutes_late=None, marked_at=timezone.now())

        return HttpResponseRedirect(request.META.get("HTTP_REFERER"))
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@login_required
def setup(request):
    """Setup process."""
    context = {
        "academic_year": AcademicYear.objects.all()
    }
    return render(request, "att/setup.html", context)


# TODO Add/remove lessons and att records automatically when changing academic year dates.
@login_required
def setup_calendar(request):
    year = AcademicYear.objects.all()[0]

    if request.method == 'POST':
        form = AcademicYearForm(request.POST, instance=year)
        if form.is_valid():
            form.save()
            return render(request, 'att/setup.html')

    else:
        form = AcademicYearForm(instance=year)

    return render(request, 'att/setup_calendar.html', {'form': form})

@login_required
def setup_teachers(request):
    return render(request, "att/setup_teachers.html")

def process_teachers_file(csvfile):
    with TextIOWrapper(csvfile, encoding='utf-8', newline='\n') as csv_text_file:
        reader = csv.reader(csv_text_file)
        for row in reader:
            u = User.objects.create_user(row[7].lower(), row[7].lower())
            teacher = Teacher(user=u, first_name=row[1], last_name=row[2])
            teacher.save()

@require_POST
@login_required
def import_teachers(request):
    process_teachers_file(request.FILES["teachers-file"])
    return render(request, "att/setup.html")

@login_required
def setup_students(request):
    return render(request, "att/setup_students.html")

def process_students_file(csvfile):
    with TextIOWrapper(csvfile, encoding='utf-8', newline='\n') as csv_text_file:
        reader = csv.reader(csv_text_file)
        for row in reader:
            osection = row[7].replace('-', '')
            s = Section.objects.get(name=osection)
            osemail = row[4]
            osfirstname = row[3]
            oslastname = row[1] + ' ' + row[2]
            student = Student(email=osemail, first_name=osfirstname, last_name=oslastname, section=s)
            print(student)
            student.save()

@require_POST
@login_required
def import_students(request):
    process_students_file(request.FILES["students-file"])
    return render(request, "att/setup.html")


@login_required
def setup_courses(request):
    return render(request, "att/setup_courses.html")

def temp_folder():
    return Path("att/utils/tmp")

def clean_temp_folder():
    for file in temp_folder().glob('*'):
        file.unlink()

def save_to_temp(f):
    with open(f"{temp_folder()}/{f}", "wb+") as tempxls:
        for chunk in f.chunks():
            tempxls.write(chunk)

def xls_to_csv(folder):
    for xlsfile in folder.glob(f'*.xls'):
        if xlsfile.is_file():
            excel = xlrd.open_workbook(str(xlsfile))
            sheet = excel.sheet_by_index(0)
            with open(folder / (xlsfile.stem + ".csv"), 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                for row in range(sheet.nrows):
                    writer.writerow(sheet.row_values(row))

def delete_course_files(folder):
    for f in folder.glob(f'*.*'):
        if f.is_file():
            f.unlink()

def add_enrolments(course, student_emails, test=False):
    for student_email in student_emails:
        student = Student.objects.get(email=student_email)
        enrolment = Enrolment(student=student, course=course)
        if test:
            pass
        else:
            enrolment.save()


def process_course_files(folder, test=False):
    for csvfile in temp_folder().glob(f'*.csv'):
        if csvfile.is_file():
            parser = Parser()
            course_data = parser.parse(csvfile)
            try:
                t = Teacher.objects.annotate(fname = Concat('first_name', Value(' '), 'last_name')).get(fname=course_data['teacher'].strip())
                course = Course(name=f'{course_data["name"]} - {course_data["sections"]}',
                                level=12,
                                teacher=t,
                                weekly_sessions=4)
                if test:
                    print(course)
                else:
                    course.save()
                    add_enrolments(course, course_data['students'], test)
            except Exception as e:
                print(f"Couldn't find a teacher called {course_data['teacher'].strip()}")

@require_POST
@login_required
def import_courses(request):
    clean_temp_folder()
    for f in request.FILES.getlist("courses-file"):
        save_to_temp(f)
    xls_to_csv(temp_folder())
    process_course_files(temp_folder(), False)
    delete_course_files(temp_folder())
    return render(request, "att/setup.html")

class SetupTimetables(LoginRequiredMixin, generic.ListView):
    """Setup courses' weekly timetables."""
    template_name = "att/setup_timetables.html"
    model = Course

    def get_queryset(self):
        return Course.objects.order_by("name").annotate(pending_sessions=F("weekly_sessions")-Count("weeklyschedule"))

class SetupTimetable(LoginRequiredMixin, generic.ListView):
    """Setup a specific course's weekly timetable."""
    template_name = "att/setup_timetable.html"
    model = WeeklySchedule
    context_object_name = "schedules"

    def get_queryset(self):
        self.course = get_object_or_404(Course, pk=self.kwargs["pk"])
        return WeeklySchedule.objects.filter(course=self.course)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = self.course
        context["periods"] = Period.objects.all()
        buttons = []
        for p in Period.objects.all():
            buttonsrow = {"period": p, "buttons": []}
            for d in range(1,6):
                if WeeklySchedule.objects.filter(course=self.course, iso_weekday=d, period=p).first():
                    buttonsrow["buttons"].append({"day": d, "scheduled": True})
                else:
                    buttonsrow["buttons"].append({"day": d, "scheduled": False})
            buttons.append(buttonsrow)
        context["buttons"] = buttons
        return context


@require_POST
@login_required
def toggle_schedule(request):
    data = json.loads(request.body)
    try:
        course_id = int(data["courseId"])
        period_id = int(data["periodId"])
        iso_weekday = int(data["day"])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"error": "Invalid or missing parameters"}, status=400)

    if not (1 <= iso_weekday <= 7):
        return JsonResponse({"error": "Weekday must be between 1 and 7"}, status=400)

    try:
        c = Course.objects.get(pk=course_id)
        p = Period.objects.get(pk=period_id)
    except Course.DoesNotExist:
        return JsonResponse({"error": "Course not found"}, status=400)
    except Period.DoesNotExist:
        return JsonResponse({"error": "Period not found"}, status=400)

    course_start = AcademicYear.objects.all()[0].start_date
    course_end = AcademicYear.objects.all()[0].end_date + timedelta(days=1)

    with transaction.atomic():
        existing = WeeklySchedule.objects.filter(
            course=c,
            iso_weekday=iso_weekday,
            period=p
        ).first()
        if existing:
            do_delete_lessons(existing, course_start, course_end)
            existing.delete()
            status = "deleted"
        else:
            schedule = WeeklySchedule(course=c, iso_weekday=iso_weekday, period=p)
            schedule.save()
            do_generate_lessons_and_att_records(ws=schedule, from_date=course_start, to_date=course_end)
            status = "created"

    return JsonResponse({"status": status, "course": c.id, "iso_weekday": iso_weekday, "period": p.id})

class SetupNonSchoolDays(generic.ListView):
    """Setup non-school days in calendar."""
    template_name = "att/setup_nonschool_days.html"
    model = NonSchoolDay

# TODO Remove the ability to generate lessons directly.
# They should be added or removed automatically by scheduling weekly lessons.

@login_required
def setup_lessons(request):
    return render(request, "att/setup_lessons.html")

@require_POST
@login_required
def generate_lessons(request):
    results = do_generate_all_lessons()
    return JsonResponse({"status": "ok", "lesson_num": results})

# TODO Remove the ability to generate attendance records directly.
# They should be added or removed automatically by scheduling weekly lessons.

@login_required
def setup_attendance_records(request):
    return render(request, "att/setup_attendance_records.html")

@require_POST
@login_required
def generate_attendance_records(request):
    results = do_generate_all_attendance_records()
    return JsonResponse({"status": "ok", "att_record_num": results})
