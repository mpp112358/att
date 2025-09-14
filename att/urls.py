#!/usr/bin/env python

from django.urls import path

from . import views

app_name = "att"

urlpatterns =[
    path("", views.landing_view, name="index"),
    path("unauthorised/", views.unauthorised, name="unauthorised"),
    path("today/", views.LessonsToday.as_view(), name="lessons-today"),
    path("<int:year>/<str:month>/<int:day>/", views.LessonsOnDay.as_view(), name="lessons-on-day"),
    path("student/<int:student_id>/<int:year>/<int:month>/<int:day>/", views.student_on_day, name="student-on-day"),
    path("student-week/<int:student_id>/<int:year>/<int:month>/<int:day>/", views.StudentWeekView.as_view(), name="student-week"),
    path("week/<int:year>/<int:month>/<int:day>/", views.WeekView.as_view(), name="week-view"),
    path("current-week/", views.CurrentWeekView.as_view(), name="current-week"),
    path("lesson/<int:lesson_id>/", views.lesson_detail, name="lesson-detail"),
    path("mark-attendance/", views.mark_attendance, name="mark-attendance"),
    path("mark-unregistered-present/", views.mark_unregistered_present, name="mark-unregistered-present"),
    path("report-day/<int:year>/<int:month>/<int:day>/", views.report_day, name="report-day"),
    path("report-today/", views.report_today, name="report-today"),
    path("report-from/<int:year>/<int:month>/<int:day>/", views.report_from, name="report-from"),
    path("report-from-start/", views.report_from_start, name="report-from-start"),
    path("report-student-select/", views.report_student_select, name="report-student-select"),
    path("report-student/<int:student_id>/", views.report_student, name="report-student"),
    path("select-student/", views.select_student, name="select-student"),
    path("search-student/", views.search_student, name="search-student"),
    path("do-search-students/", views.do_search_students, name="do-search-students"),
    path("select-student/", views.select_student, name="select-student"),
    path("setup/", views.setup, name="setup"),
    path("setup-calendar/", views.setup_calendar, name="setup-calendar"),
    path("setup-teachers/", views.setup_teachers, name="setup-teachers"),
    path("import-teachers/", views.import_teachers, name="import-teachers"),
    path("setup-students/", views.setup_students, name="setup-students"),
    path("import-students/", views.import_students, name="import-students"),
    path("setup-courses/", views.setup_courses, name="setup-courses"),
    path("import-courses/", views.import_courses, name="import-courses"),
    path("setup-timetables/", views.SetupTimetables.as_view(), name="setup-timetables"),
    path("setup-timetable/<int:pk>/", views.SetupTimetable.as_view(), name="setup-timetable"),
    path("toggle-schedule/", views.toggle_schedule, name="toggle-schedule"),
    path("setup-nonschool-day/", views.SetupNonSchoolDays.as_view(), name="setup-nonschool-days"),
    path("setup-lessons/", views.setup_lessons, name="setup-lessons"),
    path("generate-lessons/", views.generate_lessons, name="generate-lessons"),
    path("setup-attendance-records/", views.setup_attendance_records, name="setup-attendance-records"),
    path("generate-attendance-records/", views.generate_attendance_records, name="generate-attendance-records")
]
