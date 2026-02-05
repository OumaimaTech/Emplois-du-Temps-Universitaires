from datetime import time, datetime, timedelta
from models import Course, Room, Group, TimeSlot, TeacherAvailability
import random

class TimetableGenerator:
    """Générateur d'emploi du temps avec backtracking intelligent."""

    def __init__(self, department_id, semester, start_date=None, end_date=None, group_id=0, debug=False):
        self.department_id = department_id
        self.semester = semester
        self.start_date = start_date 
        self.end_date = end_date
        self.group_id = group_id  # 0 signifie tous les groupes du département
        self.generated_slots = []
        self.conflicts = []
        self.debug = debug
        self.slot_starts = [
            time(8, 0), time(9, 0), time(10, 0), time(11, 0),
            time(12, 0), time(13, 0), time(14, 0), time(15, 0),
            time(16, 0), time(17, 0)
        ]
        self.days = [0, 1, 2, 3, 4, 5]

    def generate(self):
        """Génère l'emploi du temps pour les groupes spécifiés."""
        if self.group_id and self.group_id != 0:
            groups = Group.query.filter_by(id=self.group_id).all()
        else:
            groups = Group.query.filter_by(department_id=self.department_id).all()
        
        if not groups:
            return {"error": "Aucun groupe trouvé"}

        all_rooms = Room.query.all()
        generated_count = 0
        failed_count = 0
        for group in groups:
            courses = group.courses
            
            for course in courses:
                sessions_needed = course.weekly_sessions if hasattr(course, 'weekly_sessions') else 1
                duration_min = course.duration_minutes if course.duration_minutes else 60
                
                for _ in range(sessions_needed):
                    scheduled = False
                    suitable_rooms = [r for r in all_rooms if (r.room_type == 'Lab') == course.requires_lab]
                    random.shuffle(suitable_rooms)
                    random.shuffle(self.days)
                    available_teachers = course.teachers
                    if not available_teachers:
                        self.conflicts.append({
                            "course": course.name,
                            "group": group.name,
                            "reason": "Aucun enseignant assigné à ce cours"
                        })
                        failed_count += 1
                        continue

                    for day in self.days:
                        if scheduled: break
                        current_starts = self.slot_starts[:]
                        random.shuffle(current_starts)

                        for start_time in current_starts:
                            if scheduled: break
                            end_time = self.add_minutes(start_time, duration_min)
                            
                            if end_time > time(17, 0):
                                continue

                            if self.check_group_busy(group.id, day, start_time, end_time):
                                continue
                                
                            selected_room = None
                            for room in suitable_rooms:
                                if not self.check_room_busy(room.id, day, start_time, end_time):
                                    selected_room = room
                                    break
                            
                            if not selected_room:
                                continue
                                
                            selected_teacher = None
                            for teacher in available_teachers:
                                if not self.check_teacher_busy(teacher.id, day, start_time, end_time):
                                    if self.check_teacher_preferences(teacher.id, day, start_time, end_time):
                                        selected_teacher = teacher
                                        break
                            
                            if not selected_teacher:
                                continue
                            new_slot = TimeSlot(
                                course_id=course.id,
                                group_id=group.id,
                                room_id=selected_room.id,
                                teacher_id=selected_teacher.id,
                                day_of_week=day,
                                start_time=start_time,
                                end_time=end_time
                            )
                            self.generated_slots.append(new_slot)
                            generated_count += 1
                            scheduled = True
                            
                    if not scheduled:
                        failed_count += 1
                        self.conflicts.append({
                            "course": course.name,
                            "group": group.name,
                            "reason": "Impossible de trouver un créneau valide"
                        })
        return {
            "generated": generated_count,
            "failed": failed_count,
            "timeslots": self.generated_slots,
            "conflicts": self.conflicts
        }

    def add_minutes(self, start_time, minutes):
        dummy_date = datetime(2000, 1, 1, start_time.hour, start_time.minute)
        new_date = dummy_date + timedelta(minutes=minutes)
        return new_date.time()

    def is_overlap(self, start1, end1, start2, end2):
        return max(start1, start2) < min(end1, end2)

    def check_group_busy(self, group_id, day, start_time, end_time):
        for slot in self.generated_slots:
            if slot.group_id == group_id and slot.day_of_week == day:
                if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                    return True
        existing = TimeSlot.query.filter_by(group_id=group_id, day_of_week=day).all()
        for slot in existing:
             if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                return True
        return False

    def check_room_busy(self, room_id, day, start_time, end_time):
        for slot in self.generated_slots:
            if slot.room_id == room_id and slot.day_of_week == day:
                if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                    return True
        existing = TimeSlot.query.filter_by(room_id=room_id, day_of_week=day).all()
        for slot in existing:
             if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                return True
        return False

    def check_teacher_busy(self, teacher_id, day, start_time, end_time):
        for slot in self.generated_slots:
            if slot.teacher_id == teacher_id and slot.day_of_week == day:
                if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                    return True
        existing = TimeSlot.query.filter_by(teacher_id=teacher_id, day_of_week=day).all()
        for slot in existing:
             if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                return True
        return False

    def check_teacher_preferences(self, teacher_id, day, start_time, end_time):
        availabilities = TeacherAvailability.query.filter_by(teacher_id=teacher_id, day_of_week=day).all()
        
        if not availabilities:
            any_avail = TeacherAvailability.query.filter_by(teacher_id=teacher_id).first()
            if not any_avail:
                return True
            return False
            
        for avail in availabilities:
            if avail.is_available:
                if avail.start_time <= start_time and avail.end_time >= end_time:
                    return True
        return False

    def save_timetable(self, db):
        try:
            for slot in self.generated_slots:
                db.session.add(slot)
            db.session.commit()
            return len(self.generated_slots)
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de la sauvegarde de l'emploi du temps : {e}")
            return 0
