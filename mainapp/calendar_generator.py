# https://www.huiwenteo.com/normal/2018/07/24/django-calendar.html


from datetime import datetime
from calendar import HTMLCalendar
from . import tools


class Calendar(HTMLCalendar):
    def __init__(self, year=None, month=None):
        self.year = year
        self.month = month
        super(Calendar, self).__init__()

    # formats a day as a td
    # filter events by day
    def formatday(self, day, events, request):
        events_per_day = [
            event
            for event in events
            if datetime.fromisoformat(event["end"]["dateTime"]).day == day
        ]
        d = ""
        for event in events_per_day:
            d += f"""
			<div style="z-index:9999; padding-left:10%; padding-right:10%; width:100%;border-radius:1.5vh;color:{"white" if not tools.is_checked_off(request, event) else "gray"};margin-bottom:5px; background-color:{tools.get_color(request, event['description'])}; display: -webkit-box;
                -webkit-line-clamp: 4;
                -webkit-box-orient: vertical;
                overflow:hidden;
                overflow-wrap:break-word;
                max-width:15vw;
                ">
				{event['summary']}
			</div>
			"""

        if day != 0:
            return f"<td><span class='date'>{day}</span><ul> {d} </ul></td>"
        return "<td></td>"

    # formats a week as a tr
    def formatweek(self, theweek, events, request):
        week = ""
        for d, _ in theweek:
            week += self.formatday(d, events, request)
        return f"<tr> {week} </tr>"

    # formats a month as a table
    # filter events by year and month

    def formatmonth(self, request, withyear=True):
        print("Grabbing month", self.month)
        events = tools.get_events(request, month=self.month, year=self.year)
        cal = f'<table border="0" cellpadding="0" cellspacing="0" class="calendar">\n'
        cal += f"{self.formatmonthname(self.year, self.month, withyear=withyear)}\n"
        cal += f"{self.formatweekheader()}\n"
        for week in self.monthdays2calendar(self.year, self.month):
            cal += f"{self.formatweek(week, events, request)}\n"
        return cal

