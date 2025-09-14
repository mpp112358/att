#!/usr/bin/env python
import csv

class State(object):
    def __init__(self, parser):
        self.parser = parser

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.__class__.__name__

    def on_event(self, event):
        pass

class FindStudent(State):
    def on_event(self, event):
        if event['col'] == self.parser.cols['students_col']:
            if event['value']:
                self.parser.add_student(event)
        return FindStudent(self.parser)

class FindStudentsCol(State):
    def on_event(self, event):
        if event['value'] == 'Anotaciones':
            self.parser.set_students_col(event)
            return FindStudent(self.parser)
        return FindStudentsCol(self.parser)

class FindSections(State):
    def on_event(self, event):
        if event['col'] == self.parser.cols['subject_col']:
            if event['value']:
                self.parser.set_sections(event)
                return FindStudentsCol(self.parser)

        return FindSections(self.parser)

class FindTeacher(State):
    def on_event(self, event):
        if event['col'] == self.parser.cols['subject_col']:
            if event['value']:
                self.parser.set_teacher(event)
                return FindSections(self.parser)
        return FindTeacher(self.parser)


class FindSubjectName(State):
    def on_event(self, event):
        if event['value']:
            self.parser.set_subject(event)
            return FindTeacher(self.parser)
        return FindSubjectName(self.parser)

class FindSubject(State):
    def on_event(self, event):
        if event['value'] == 'Materia:':
            return FindSubjectName(self.parser)
        return FindSubject(self.parser)

class Parser():
    def __init__(self) -> None:
        self.cols = {'subject_col': None, 'students_col': None}
        self.course = {'name': None, 'teacher': None, 'sections': [], 'students': []}
        self.state = FindSubject(self)

    def set_subject(self, event):
        self.course['name'] = event['value']
        self.cols['subject_col'] = event['col']

    def set_teacher(self, event):
        self.course['teacher'] = event['value']

    def set_sections(self, event):
        self.course['sections'] = event['value']

    def set_students_col(self, event):
        self.cols['students_col'] = event['col']

    def add_student(self, event):
        self.course['students'].append(event['value'])

    def reset(self):
        self.cols = {'subject_col': None, 'students_col': None}
        self.course = {'name': None, 'teacher': None, 'sections': [], 'students': []}
        self.state = FindSubject(self)

    def parse(self, csvfile):
        with open(csvfile, 'r', encoding='utf-8', newline='\n') as f:
            reader = csv.reader(f)
            for row_index, row in enumerate(reader):
                for col_index, field in enumerate(row):
                    self.state = self.state.on_event({'row': row_index, 'col': col_index, 'value': field.strip()})
        return self.course
