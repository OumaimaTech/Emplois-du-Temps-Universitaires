from models import TimeSlot, Group, TeacherAvailability
from datetime import datetime, date, timedelta

class ConflictDetector:
    """Détecte les conflits dans l'emploi du temps."""
    
    def __init__(self):
        self.conflicts = []
    
    def detect_room_conflicts(self):
        timeslots = TimeSlot.query.all()
        checked_pairs = set()

        for slot in timeslots:
            overlapping = TimeSlot.query.filter(
                TimeSlot.id != slot.id,
                TimeSlot.room_id == slot.room_id,
                TimeSlot.day_of_week == slot.day_of_week,
                TimeSlot.start_time < slot.end_time,
                TimeSlot.end_time > slot.start_time
            ).all()
            
            if overlapping:
                for conflict_slot in overlapping:
                    pair_key = tuple(sorted((slot.id, conflict_slot.id)))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)

                    self.conflicts.append({
                        'type': 'room_conflict',
                        'severity': 'critical',
                        'room': slot.room.name,
                        'slot1_course': slot.course.name,
                        'slot2_course': conflict_slot.course.name,
                        'description': f'Salle {slot.room.name} réservée en double le jour {slot.day_of_week}'
                    })
        return [c for c in self.conflicts if c['type'] == 'room_conflict']
    
    def detect_teacher_conflicts(self):
        timeslots = TimeSlot.query.all()
        checked_pairs = set()

        for slot in timeslots:
            overlapping = TimeSlot.query.filter(
                TimeSlot.id != slot.id,
                TimeSlot.teacher_id == slot.teacher_id,
                TimeSlot.day_of_week == slot.day_of_week,
                TimeSlot.start_time < slot.end_time,
                TimeSlot.end_time > slot.start_time
            ).all()
            
            if overlapping:
                for conflict_slot in overlapping:
                    pair_key = tuple(sorted((slot.id, conflict_slot.id)))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)
                    self.conflicts.append({
                        'type': 'teacher_conflict',
                        'severity': 'critical',
                        'teacher': slot.teacher.full_name if slot.teacher else 'Inconnu',
                        'slot1_course': slot.course.name,
                        'slot2_course': conflict_slot.course.name,
                        'description': f"L'enseignant {slot.teacher.full_name} a deux cours en même temps"
                    })
        return [c for c in self.conflicts if c['type'] == 'teacher_conflict']

    def detect_group_conflicts(self):
        timeslots = TimeSlot.query.all()
        checked_pairs = set()

        for slot in timeslots:
            if not slot.group_id: continue
            overlapping = TimeSlot.query.filter(
                TimeSlot.id != slot.id,
                TimeSlot.group_id == slot.group_id,
                TimeSlot.day_of_week == slot.day_of_week,
                TimeSlot.start_time < slot.end_time,
                TimeSlot.end_time > slot.start_time
            ).all()
            
            if overlapping:
                for conflict_slot in overlapping:
                    pair_key = tuple(sorted((slot.id, conflict_slot.id)))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)
                    self.conflicts.append({
                        'type': 'group_conflict',
                        'severity': 'critical',
                        'group': slot.group.name,
                        'slot1_course': slot.course.name,
                        'slot2_course': conflict_slot.course.name,
                        'description': f'Le groupe {slot.group.name} a deux cours en même temps'
                    })
        return [c for c in self.conflicts if c['type'] == 'group_conflict']

    def detect_availability_conflicts(self):
        timeslots = TimeSlot.query.all()
        
        for slot in timeslots:
            if not slot.teacher_id: continue
            avail = TeacherAvailability.query.filter_by(
                teacher_id=slot.teacher_id,
                day_of_week=slot.day_of_week
            ).first()
            
            is_valid = False
            if avail and avail.is_available:
                if avail.start_time <= slot.start_time and avail.end_time >= slot.end_time:
                    is_valid = True
            
            if not is_valid:
                 self.conflicts.append({
                    'type': 'availability_conflict',
                    'severity': 'high',
                    'teacher': slot.teacher.full_name,
                    'course': slot.course.name,
                    'time': f"{slot.start_time}-{slot.end_time}",
                    'description': f"L'enseignant {slot.teacher.full_name} n'est pas disponible à cette heure"
                })
        return [c for c in self.conflicts if c['type'] == 'availability_conflict']

    def detect_workload_violations(self):
        groups = Group.query.all()
        
        for group in groups:
            slots = TimeSlot.query.filter_by(group_id=group.id).all()
            total_minutes = 0
            for slot in slots:
                d1 = datetime.combine(date.min, slot.end_time) - datetime.combine(date.min, slot.start_time)
                total_minutes += d1.total_seconds() / 60
            
            total_hours = total_minutes / 60.0
            
            if total_hours < 18 or total_hours > 24:
                self.conflicts.append({
                    'type': 'workload_conflict',
                    'severity': 'medium',
                    'group': group.name,
                    'hours': total_hours,
                    'description': f'Groupe {group.name} : charge horaire {total_hours}h/semaine (Requis: 18h-24h)'
                })
        return [c for c in self.conflicts if c['type'] == 'workload_conflict']

    def detect_capacity_conflicts(self):
        timeslots = TimeSlot.query.all()
        
        for slot in timeslots:
            if slot.group:
                students_count = getattr(slot.group, 'student_count', 30)
            else:
                students_count = 0
            
            if students_count > slot.room.capacity:
                self.conflicts.append({
                    'type': 'capacity_conflict',
                    'severity': 'high',
                    'room': slot.room.name,
                    'required': students_count,
                    'capacity': slot.room.capacity,
                    'description': f'Capacité de la salle {slot.room.name} ({slot.room.capacity}) insuffisante pour {students_count} étudiants'
                })
        return [c for c in self.conflicts if c['type'] == 'capacity_conflict']
    
    def detect_all_conflicts(self):
        self.conflicts = []
        self.detect_room_conflicts()
        self.detect_teacher_conflicts()
        self.detect_group_conflicts()
        self.detect_availability_conflicts()
        self.detect_workload_violations()
        self.detect_capacity_conflicts()
        
        return {
            'total_conflicts': len(self.conflicts),
            'critical': len([c for c in self.conflicts if c['severity'] == 'critical']),
            'high': len([c for c in self.conflicts if c['severity'] == 'high']),
            'medium': len([c for c in self.conflicts if c['severity'] == 'medium']),
            'conflicts': self.conflicts
        }
