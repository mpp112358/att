from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import re

# Create your models here.

class AcademicYear(models.Model):
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.name}"

class Section(models.Model):
    name = models.CharField(max_length=100)
    level = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.name}"

class Student(models.Model):
    email = models.EmailField()
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.full_name}"

class Course(models.Model):
    name = models.CharField(max_length=100)
    level = models.PositiveSmallIntegerField()
    teacher = models.ForeignKey(Teacher, null=True, blank=True, on_delete=models.SET_NULL)
    weekly_sessions = models.SmallIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}"

    def shorten_name(self):
        maxlength = 20
        sectionsre = '.* - (\\d[ABCD])?,? ?(\\d[ABCD])?,? ?(\\d[ABCD])?,? ?(\\d[ABCD])?'
        m = re.search(sectionsre, self.name.replace('BAC', '').replace('ESO', ''))
        sections = [m.group(i) for i in range(1, m.lastindex + 1)]
        sectionsstr = ','.join(sections)
        remaining = maxlength - len(sectionsstr) - 4
        return self.name[0:remaining] + "... " + sectionsstr


class Period(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.name}"

class Enrolment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("student", "course")

    def __str__(self):
        return f"{self.student} is enrolled in {self.course}"

class WeeklySchedule(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    iso_weekday = models.PositiveSmallIntegerField()
    period = models.ForeignKey(Period, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.course} scheduled for period {self.period} on {self.iso_weekday}"

class Classroom(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name}"

class NonSchoolDay(models.Model):
    date = models.DateField()

    def __str__(self):
        return f"{self.date}"

class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, null=True, blank=True, on_delete=models.SET_NULL)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    date = models.DateField()
    classroom = models.ForeignKey(Classroom, null=True, blank=True, on_delete=models.SET_NULL)
    start_datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.course} on {self.date} ({self.period})"

class AttendanceStatus(models.TextChoices):
    UNREGISTERED = "unregistered", "Unregistered"
    PRESENT = "present", "Present"
    ABSENT = "absent", "Absent"
    LATE = "late", "Late"

class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    minutes_late = models.PositiveIntegerField(null=True, blank=True)
    marked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'lesson')

    # def clean(self):
    #     super().clean()

    #     if self.status == AttendanceStatus.LATE and self.minutes_late is None:
    #         raise ValidationError({
    #             "minutes_late": "You must specifiy how many minutes late the student was."
    #         })

    #     if self.status != AttendanceStatus.LATE and self.minutes_late is not None:
    #         raise ValidationError({
    #             "minutes_late": "Minutes late should be empty unless the student was late."
    #         })

    def __str__(self):
        return f"{self.student} enrolled in {self.lesson}"

