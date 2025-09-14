from django.contrib import admin

from .models import Teacher, Section, Student, Course, Enrolment, Period, WeeklySchedule, Classroom, AcademicYear, NonSchoolDay, Lesson, AttendanceRecord

# Register your models here.

admin.site.register(Teacher)
admin.site.register(Section)
admin.site.register(Student)
admin.site.register(Course)
admin.site.register(Enrolment)
admin.site.register(Period)
admin.site.register(WeeklySchedule)
admin.site.register(Classroom)
admin.site.register(AcademicYear)
admin.site.register(NonSchoolDay)
admin.site.register(Lesson)
admin.site.register(AttendanceRecord)
