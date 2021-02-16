# -*- coding: utf-8 -*-
""" tabview.py -- View a tab-delimited file in a spreadsheet-like display.
  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>
  Modified by Alfio Rizzo for pvValidator
"""
import csv
import _curses
import curses
import curses.ascii
import locale
#import io
import os
import re
import string
import sys
from collections import Counter
from curses.textpad import Textbox
from operator import itemgetter
from textwrap import wrap
import unicodedata
#import shlex










class ReloadException(Exception):
    def __init__(self, start_pos, column_width, column_gap, column_widths,
                 search_str):
        self.start_pos = start_pos
        self.column_width_mode = column_width
        self.column_gap = column_gap
        self.column_widths = column_widths
        self.search_str = search_str


class QuitException(Exception):
    pass


class Viewer:
    """The actual viewer class.
    Args:
        args: other positional arguments. See view() for descriptions.
            stdscr, data
        kwargs: dict of other keyword arguments.
            start_pos, column_width, column_gap, trunc_char, column_widths,
            search_str, double_width
    """
    def __init__(self, *args, **kwargs):
        # Fix for python curses resize bug:
        # http://bugs.python.org/issue2675
        os.unsetenv('LINES')
        os.unsetenv('COLUMNS')
        self.scr = args[0]
        self.data = [[str(j) for j in i] for i in args[1]]
        self.info = kwargs.get('info')
        self.header_offset_orig = 7
        self.header = self.data[0]
        self.Title = kwargs.get('Title')
        self.datainfo = kwargs.get('datainfo')
        self.summarytitle = kwargs.get('sumtitle')
        self.ioctitle = kwargs.get('ioctitle')
        self.sread = kwargs.get('readme')
        self.searchres = False
        if len(self.data) > 1 and \
                not any(self._is_num(cell) for cell in self.header):
            del self.data[0]
            self.header_offset = self.header_offset_orig
        else:
            # Don't make one line file a header row
            # If any of the header line cells are all digits, assume that the
            # first line is NOT a header
            self.header_offset = self.header_offset_orig - 1
        self.num_data_columns = len(self.data[0])
        self._init_double_width(kwargs.get('double_width'))
        self.column_width_mode = kwargs.get('column_width')
        self.column_gap = kwargs.get('column_gap')
        self._init_column_widths(kwargs.get('column_width'),
                                 kwargs.get('column_widths'))
        try:
            kwargs.get('trunc_char').encode(sys.stdout.encoding or 'utf-8')
            self.trunc_char = kwargs.get('trunc_char')
        except (UnicodeDecodeError, UnicodeError):
            self.trunc_char = '>'

        self.x, self.y = 0, 0
        self.win_x, self.win_y = 0, 0
        self.max_y, self.max_x = 0, 0
        self.num_columns = 0
        self.vis_columns = 0
        self.init_search = self.search_str = kwargs.get('search_str')
        self._input_win_open = 0
        self.modifier = str()
        self.define_keys()
        self.resize()
        self.display()
        # Handle goto initial position (either (y,x), [y] or y)
        try:
            self.goto_y(kwargs.get('start_pos')[0])
        except TypeError:
            self.goto_y(kwargs.get('start_pos'))
        try:
            self.goto_x(kwargs.get('start_pos')[1])
        except (IndexError, TypeError):
            pass

    def addstr(self,*args):
        scr, args = args[0], args[1:]
        return scr.addstr(*args)

    def insstr(self,*args):
        scr, args = args[0], args[1:]
        return scr.insstr(*args)


    def _is_num(self, cell):
        try:
            float(cell)
            return True
        except ValueError:
            return False

    def _init_double_width(self, dw):
        """Initialize self._cell_len to determine if double width characters
        are taken into account when calculating cell widths.
        """
        self.double_width = dw
        # Enable double with character processing for small files
        if self.double_width is False:
            self.double_width = len(self.data) * self.num_data_columns < 65000
        if self.double_width is True:
            self._cell_len = self.__cell_len_dw
        else:
            self._cell_len = len

    def _init_column_widths(self, cw, cws):
        """Initialize column widths
        Args: - cw: column_width mode
                cws: list of column widths
        """
        if cws is None or len(self.data[0]) != len(cws):
            self._get_column_widths(cw)
        else:
            self.column_width = cws

    def column_xw(self, x):
        """Return the position and width of the requested column"""
        xp = sum(self.column_width[self.win_x:self.win_x + x]) \
            + x * self.column_gap
        w = max(0, min(self.max_x - xp, self.column_width[self.win_x + x]))
        return xp, w

    def quit(self):
        raise QuitException

    def reload(self):
        start_pos = (self.y + self.win_y + 1, self.x + self.win_x + 1)
        raise ReloadException(start_pos, self.column_width_mode,
                              self.column_gap, self.column_width,
                              self.search_str)

    def consume_modifier(self, default=1):
        m = int(self.modifier) if len(self.modifier) else default
        self.modifier = str()
        return m

    def down(self):
        m = self.consume_modifier()
        yp = self.y + self.win_y
        self.goto_y(yp + 1 + m)

    def up(self):
        m = self.consume_modifier()
        yp = self.y + self.win_y
        self.goto_y(yp + 1 - m)

    def left(self):
        m = self.consume_modifier()
        xp = self.x + self.win_x
        self.goto_x(xp + 1 - m)

    def right(self):
        m = self.consume_modifier()
        xp = self.x + self.win_x
        self.goto_x(xp + 1 + m)

    def page_down(self):
        m = self.consume_modifier()
        row_shift = (self.max_y - self.header_offset) * m
        end = len(self.data) - 1
        if self.win_y <= end - row_shift:
            new_win_y = self.win_y + row_shift
            if new_win_y + self.y > end:
                self.y = end - new_win_y
            self.win_y = new_win_y
        else:
            self.y = end - self.win_y

    def page_up(self):
        m = self.consume_modifier()
        row_shift = (self.max_y - self.header_offset) * m
        if self.win_y == 0:
            self.y = 0
        elif self.win_y < row_shift:
            self.win_y = 0
        else:
            self.win_y = self.win_y - row_shift

    def page_right(self):
        for _ in range(self.consume_modifier()):
            end = self.num_data_columns - 1
            if self.win_x <= end - self.num_columns:
                cols = self.num_columns_fwd(self.win_x + self.x)
                new_win_x = self.win_x + cols
                if new_win_x + self.x > end:
                    self.x = end - new_win_x
                self.win_x = new_win_x
                self.recalculate_layout()
            else:
                self.x = end - self.win_x
                break

    def page_left(self):
        for _ in range(self.consume_modifier()):
            if self.win_x == 0:
                self.x = 0
                break
            cols = self.num_columns_rev(self.win_x + self.x)
            if self.win_x < cols:
                self.win_x = 0
                self.recalculate_layout()
            else:
                self.win_x = self.win_x - cols
                self.recalculate_layout()

    def mark(self):
        self.save_y, self.save_x = self.y + self.win_y, self.x + self.win_x

    def goto_mark(self):
        if hasattr(self, 'save_y'):
            self.goto_yx(self.save_y + 1, self.save_x + 1)

    def home(self):
        self.goto_y(1)

    def goto_y(self, y):
        y = max(min(len(self.data), y), 1)
        if self.win_y < y <= self.win_y + \
                (self.max_y - self.header_offset - self._input_win_open):
            # same screen, change y appropriately.
            self.y = y - 1 - self.win_y
        elif y <= self.win_y:
            # going back
            self.y = 0
            self.win_y = y - 1
        else:
            # going forward
            self.win_y = y - (self.max_y - self.header_offset -
                              self._input_win_open)
            self.y = (self.max_y - self.header_offset -
                      self._input_win_open) - 1

    def goto_row(self):
        m = self.consume_modifier(len(self.data))
        self.goto_y(m)

    def goto_x(self, x):
        x = max(min(self.num_data_columns, x), 1)
        if self.win_x < x <= self.win_x + self.num_columns:
            # same screen, change x value appropriately.
            self.x = x - 1 - self.win_x
        elif x <= self.win_x:
            # going back
            self.x = 0
            self.win_x = x - 1
            self.recalculate_layout()
        else:
            # going forward
            cols = self.num_columns_rev(x - 1)
            self.win_x = x - cols
            self.x = cols - 1
            self.recalculate_layout()

    def goto_col(self):
        m = self.consume_modifier()
        self.goto_x(m)

    def goto_yx(self, y, x):
        self.goto_y(y)
        self.goto_x(x)

    def line_home(self):
        self.goto_x(1)

    def line_end(self):
        end = len(self.data[self.y + self.win_y])
        self.goto_x(end)

    def show_cell(self):
        "Display current cell in a pop-up window"
        yp = self.y + self.win_y
        xp = self.x + self.win_x
        s = "\n" + self.data[yp][xp]
        if not s:
            # Only display pop-up if cells have contents
            return
        TextBox(self.scr, data=s, title=self.location_string(yp, xp))()
        self.resize()
    
    def show_row(self):
        yp = self.y + self.win_y
        #xp = self.x + self.win_x
        d = self.data[yp][6]

        if (self.datainfo is not None):
            s = "\n"+self.datainfo[d]
        else:
            return
        TextBox(self.scr, data=s, title=self.summarytitle+" --> "+d)()
        self.resize()

    def show_info(self):
        """Display program information in a pop-up window
        """
        s = "\n"+self.info 
        
        TextBox(self.scr, data=s, title=self.ioctitle)()
        self.resize()
      
    def readme(self):
        s = "\n"+self.sread
        TextBox(self.scr, data=s, title="README")()
        self.resize()


    def _search_validator(self, ch):
        """Fix Enter and backspace for textbox.
        Used as an aux function for the textpad.edit method
        """
        if ch == curses.ascii.NL:  # Enter
            return curses.ascii.BEL
        elif ch == 127:  # Backspace
            self.search_str = self.textpad.gather().strip().lower()[:-1]
            return 8
        else:
            if 0 < ch < 256:
                c = chr(ch)
                if c in string.printable:
                    res = self.textpad.gather().strip().lower()
                    self.search_str = res + chr(ch)
                    self.search_str = self.search_str.lower().strip() 
                    self.search_results(look_in_cur=True)
                    self.display()
            return ch
    
    
    def _input_validator(self,ch):
        if ch == curses.ascii.NL:  # Enter
            return curses.ascii.BEL
        elif ch == 127:  # Backspace
            return 8
        else:
            if 0 < ch < 256:
                #c = chr(ch)
                pass

            return ch



    def search(self):
        """Open search window, get input and set the search string."""
        
        scr2 = curses.newwin(3, self.max_x -100, self.max_y - 3, 0)
        scr3 = scr2.derwin(1, self.max_x - 120, 1, 9)
        scr2.box()
        scr2.move(1, 1)
        self.addstr(scr2, "Search: ")
        scr2.refresh()
        curses.curs_set(1)
        self._input_win_open = 3
        self.textpad = Textbox(scr3, insert_mode=True)
        self.search_str = self.textpad.edit(self._search_validator)
        self.search_str = self.search_str.lower().strip()
        
        try:
            curses.curs_set(0)
        except _curses.error:
            pass
        if self.search_str:
            self.init_search = None
        self._input_win_open = 0

    def search_results(self, rev=False, look_in_cur=False):
        """Given self.search_str or self.init_search, find next result after
        current position and reposition the cursor there.
        Args: rev - True/False search backward if true
              look_in_cur - True/False start search in current cell
        """
        if not self.search_str and not self.init_search:
            return
        self.searchres = True
        self.search_str = self.search_str or self.init_search
        yp, xp = self.y + self.win_y, self.x + self.win_x
        if rev is True:
            data, yp, xp = self._reverse_data(self.data, yp, xp)
        else:
            data = self.data
        if look_in_cur is False:
            # Skip ahead/back one cell
            if xp < len(data[0]) - 1:
                xp += 1
            elif xp >= len(data[0]) - 1 and yp < len(data) - 1:
                # Skip ahead a line if at the end of the current line
                yp += 1
                xp = 0
            else:
                # Skip back to the top if at the end of the data
                yp = xp = 0
        search_order = [self._search_cur_line_r,
                        self._search_next_line_to_end,
                        self._search_next_line_from_beg,
                        self._search_cur_line_l]
        for search in search_order:
            y, x, res = search(data, yp, xp)
            if res is True:
                yp, xp = y, x
                break
        if rev is True:
            self.data, yp, xp = self._reverse_data(data, yp, xp)
        if res is True:
            self.goto_yx(yp + 1, xp + 1)

    def search_results_prev(self, rev=False, look_in_cur=False):
        """Search backwards"""
        self.search_results(rev=True, look_in_cur=look_in_cur)

    def _reverse_yp_xp(self, data, yp, xp):
        return len(data) - 1 - yp, len(data[0]) - 1 - xp

    def _reverse_data(self, data, yp, xp):
        yp, xp = self._reverse_yp_xp(data, yp, xp)
        data.reverse()
        for idx, i in enumerate(data):
            i.reverse()
            data[idx] = i
        return data, yp, xp

    def _search_cur_line_r(self, data, yp, xp):
        """ Current line first, from yp,xp to the right """
        res = False
        for x, item in enumerate(data[yp][xp:]):
            if self.search_str in item.lower():
                xp += x
                res = True
                break
        return yp, xp, res

    def _search_cur_line_l(self, data, yp, xp):
        """Last, search from beginning of current line to current position """
        res = x = False
        for x, item in enumerate(data[yp][:xp]):
            if self.search_str in item.lower():
                res = True
                break
        return yp, x, res

    def _search_next_line_to_end(self, data, yp, xp):
        """ Search from next line to the end """
        res = done = False
        for y, line in enumerate(data[yp + 1:]):
            for x, item in enumerate(line):
                if self.search_str in item.lower():
                    done = True
                    break
            if done is True:
                res = True
                yp, xp = yp + 1 + y, x
                break
        return yp, xp, res

    def _search_next_line_from_beg(self, data, yp, xp):
        """Search from beginning to line before current."""
        res = done = y = x = False
        for y, line in enumerate(data[:yp]):
            for x, item in enumerate(line):
                if self.search_str in item.lower():
                    done = True
                    break
            if done is True:
                res = True
                yp, xp = y, x
                break
        return yp, xp, res

    def help(self):
        help_txt = self.help_keys()
        TextBox(self.scr, data="".join(help_txt), title="Help")()
        self.resize()

    def toggle_header(self):
        if self.header_offset == self.header_offset_orig:
            # Turn off header row
            self.header_offset = self.header_offset - 1
            self.data.insert(0, self.header)
            self.y = self.y + 1
        else:
            if len(self.data) == 1:
                return
            # Turn on header row
            self.header_offset = self.header_offset_orig
            del self.data[self.data.index(self.header)]
            if self.y > 0:
                self.y = self.y - 1
            elif self.win_y > 0:
                # Scroll down 1 to keep cursor on the same item
                self.up()
                self.down()
                self.y = self.y - 1

    def column_gap_down(self):
        self.column_gap = max(0, self.column_gap - 1)
        self.recalculate_layout()

    def column_gap_up(self):
        self.column_gap += 1
        self.recalculate_layout()

    def column_width_all_down(self):
        self.column_width = [max(1, self.column_width[i] -
                                 max(1, int(self.column_width[i] * 0.2)))
                             for i in range(0, self.num_data_columns)]
        self.recalculate_layout()

    def column_width_all_up(self):
        self.column_width = [max(1, self.column_width[i] +
                                 max(1, int(self.column_width[i] * 0.2)))
                             for i in range(0, self.num_data_columns)]
        self.recalculate_layout()

    def column_width_down(self):
        xp = self.x + self.win_x
        self.column_width[xp] -= max(1, int(self.column_width[xp] * 0.2))
        self.recalculate_layout()

    def column_width_up(self):
        xp = self.x + self.win_x
        self.column_width[xp] += max(1, int(self.column_width[xp] * 0.2))
        self.recalculate_layout()

    def sort_by_column_numeric(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=lambda x:
                           self.float_string_key(itemgetter(xp)(x)))

    def sort_by_column_numeric_reverse(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=lambda x:
                           self.float_string_key(itemgetter(xp)(x)),
                           reverse=True)

    def sort_by_column(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=itemgetter(xp))

    def sort_by_column_reverse(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=itemgetter(xp), reverse=True)

    def sort_by_column_natural(self):
        xp = self.x + self.win_x
        self.data = self.sorted_nicely(self.data, itemgetter(xp))

    def sort_by_column_natural_reverse(self):
        xp = self.x + self.win_x
        self.data = self.sorted_nicely(self.data, itemgetter(xp), rev=True)

    def sorted_nicely(self, ls, key, rev=False):
        """ Sort the given iterable in the way that humans expect.
        From StackOverflow: http://goo.gl/nGBUrQ
        """
        def convert(text):
            return int(text) if text.isdigit() else text

        def alphanum_key(item):
            return [convert(c) for c in re.split('([0-9]+)', key(item))]

        return sorted(ls, key=alphanum_key, reverse=rev)

    def float_string_key(self, value):
        """Sort by data type first and by floating point value second,
        if possible. Used for numeric sorting
        """
        try:
            value = float(value)
        except ValueError:
            pass
        return repr(type(value)), value

    def toggle_column_width(self):
        """Toggle column width mode between 'mode' and 'max' or set fixed
        column width mode if self.modifier is set.
        """
        try:
            self.column_width_mode = min(int(self.modifier), self.max_x)
            self.modifier = str()
        except ValueError:
            if self.column_width_mode == 'mode':
                self.column_width_mode = 'max'
            else:
                self.column_width_mode = 'mode'
        self._get_column_widths(self.column_width_mode)
        self.recalculate_layout()

    def set_current_column_width(self):
        xs = self.win_x + self.x
        if len(self.modifier):
            width = int(self.modifier)
            self.modifier = str()
        else:
            width = 0
            for y in range(0, len(self.data)):
                width = max(width, self._cell_len(self.data[y][xs]))
            width = min(250, width)
        self.column_width[xs] = width
        self.recalculate_layout()

    def help_keys(self):
        keylist = str("\nKeybindings:\n"
                 "---------------\n"
                 "F1 or ?                  Show this list of keybindings\n"
                 "Cursor keys or h,j,k,l   Move the highlighted row, scrolling if required.\n"
                 "Q or q                   Quit\n"             
                 "i                        Show README in pop-up\n"
                 "Enter                    View full PV Summary in pop-up window.\n"
                 "v                        Show Validation Summary in pop-up window\n"       
                 "Ctrl-w                   Write output csv file\n"
                 "Home, ^, Ctrl-a          Move to the start of this line\n"
                 "End, $, Ctrl-e           Move to the end of this line\n"
                 "[num]|                   Goto column <num>, or first column\n"
                 "                             if num not given\n"
                 "PgUp/PgDn or J/K         Move a page up or down\n"
                 "H,L                      Page left or right\n"
                 "g                        Goto top of current column\n"
                 "[num]G                   Goto line <num> or bottom of current column\n"
                 "                             if num not given\n"
                 "Insert or m              Memorize this position\n"
                 "Delete or '              Return to memorized position (if any)\n"      
                 "/                        Search (not case sensitive, result highlighted in red)\n"
                 "n                        Next search result\n"
                 "p                        Previous search result\n"
                 "t                        Toggle fixed header row\n"
                 "< >                      Decrease/Increase column width (all columns)\n"
                 #", .                      Decrease/Increase column width (current column)\n"
                 "- +                      Decrease/Increase column gap\n"
                 "s                        Sort the table by the current column (ascending)\n"
                 "S                        Sort the table by the current column (descending)\n"
                 "a                        'Natural Sort' the table (ascending)\n"
                 "A                        'Natural Sort' the table (descending)\n"
                 "#                        Sort numerically by the current column (ascending)\n"
                 "@                        Sort numerically by the current column (descending)\n"
                 "r                        Reload data. Also resets sort order\n"
                 "[num]c                   Toggle variable column width mode (mode/max),\n"
                 "                             or set width to [num]\n"
                 "[num]C                   Maximize current column, or set width to [num]\n"
                 "[num][                   Skip to (nth) change in row value (backward)\n"
                 "[num]]                   Skip to (nth) change in row value (forward)\n"
                 "[num]{                   Skip to (nth) change in column value (backward)\n"
                 "[num]}                   Skip to (nth) change in column value (forward)")
    
        return keylist

    
    def define_keys(self):
        self.keys = {'j': self.down,
                     'k': self.up,
                     'h': self.left,
                     'l': self.right,
                     'J': self.page_down,
                     'K': self.page_up,
                     'm': self.mark,
                     "'": self.goto_mark,
                     'L': self.page_right,
                     'H': self.page_left,
                     'q': self.quit,
                     'Q': self.quit,
                     '$': self.line_end,
                     '^': self.line_home,
                     'g': self.home,
                     'G': self.goto_row,
                     '|': self.goto_col,
                     '\n': self.show_row,
                     '/': self.search,
                     'n': self.search_results,
                     'p': self.search_results_prev,
                     't': self.toggle_header,
                     '-': self.column_gap_down,
                     '+': self.column_gap_up,
                     '<': self.column_width_all_down,
                     '>': self.column_width_all_up,
                     'a': self.sort_by_column_natural,
                     'A': self.sort_by_column_natural_reverse,
                     '#': self.sort_by_column_numeric,
                     '@': self.sort_by_column_numeric_reverse,
                     's': self.sort_by_column,
                     'S': self.sort_by_column_reverse,
                     'r': self.reload,
                     'c': self.toggle_column_width,
                     'C': self.set_current_column_width,
                     ']': self.skip_to_row_change,
                     '[': self.skip_to_row_change_reverse,
                     '}': self.skip_to_col_change,
                     '{': self.skip_to_col_change_reverse,
                     '?': self.help,
                     'i': self.readme,
                     'v': self.show_info,
                     curses.KEY_F1: self.help,
                     curses.KEY_UP: self.up,
                     curses.KEY_DOWN: self.down,
                     curses.KEY_LEFT: self.left,
                     curses.KEY_RIGHT: self.right,
                     curses.KEY_HOME: self.line_home,
                     curses.KEY_END: self.line_end,
                     curses.KEY_PPAGE: self.page_up,
                     curses.KEY_NPAGE: self.page_down,
                     curses.KEY_IC: self.mark,
                     curses.KEY_DC: self.goto_mark,
                     curses.KEY_ENTER: self.show_row,
                     curses.ascii.ctrl('a'): self.line_home,
                     curses.ascii.ctrl('e'): self.line_end,
                     curses.ascii.ctrl('l'): self.scr.redrawwin, 
                     curses.ascii.ctrl('w'): self.save_csvfile
                     }

    def run(self):
        # Clear the screen and display the menu of keys
        # Main loop:
        while True:
            self.display()
            self.handle_keys()

    def handle_keys(self):
        """Determine what method to call for each keypress.
        """
        c = self.scr.getch()  # Get a keystroke
        if c == curses.KEY_RESIZE:
            self.resize()
            return
        if 0 < c < 256:
            c = chr(c)
        # Digits are commands without a modifier
        try:
            found_digit = c.isdigit()
        except AttributeError:
            # Since .isdigit() doesn't exist if c > 256, we need to catch the
            # error for those keys.
            found_digit = False
        if found_digit and (len(self.modifier) > 0 or c not in self.keys):
            self.handle_modifier(c)
        elif c in self.keys:
            self.keys[c]()
        else:
            self.modifier = str()

    def handle_modifier(self, mod):
        """Append digits as a key modifier, clear the modifier if not
        a digit.
        Args:
            mod: potential modifier string
        """
        self.modifier += mod
        if not self.modifier.isdigit():
            self.modifier = str()

    def resize(self):
        """Handle terminal resizing"""
        # Check if screen was re-sized (True or False)
        resize = self.max_x == 0 or \
            curses.is_term_resized(self.max_y, self.max_x)
        if resize is True:
            self.recalculate_layout()
            curses.resizeterm(self.max_y, self.max_x)

    def num_columns_fwd(self, x):
        """Count number of fully visible columns starting at x,
        going forward.
        """
        width = cols = 0
        while (x + cols) < self.num_data_columns \
                and width + self.column_width[x + cols] <= self.max_x:
            width += self.column_width[x + cols] + self.column_gap
            cols += 1
        return max(1, cols)

    def num_columns_rev(self, x):
        """Count number of fully visible columns starting at x,
        going reverse.
        """
        width = cols = 0
        while x - cols >= 0 \
                and width + self.column_width[x - cols] <= self.max_x:
            width += self.column_width[x - cols] + self.column_gap
            cols += 1
        return max(1, cols)

    def recalculate_layout(self):
        """Recalulate the screen layout and cursor position"""
        self.max_y, self.max_x = self.scr.getmaxyx()
        self.vis_columns = self.num_columns = self.num_columns_fwd(self.win_x)
        if self.win_x + self.num_columns < self.num_data_columns:
            xc, wc = self.column_xw(self.num_columns)
            if wc > len(self.trunc_char):
                self.vis_columns += 1
        if self.x >= self.num_columns:
            self.goto_x(self.win_x + self.x + 1)
        if self.y >= self.max_y - self.header_offset:
            self.goto_y(self.win_y + self.y + 1)

    def location_string(self, yp, xp):
        """Create (y,x) col_label string. Max 50% of screen width. (y,x) is
        padded to the max possible length it could be. Label string gets
        trunc_char appended if it's longer than the allowed width.
        """
        yx_str = "({},{})"
        #label_str = "{},{}"
        max_y = str(len(self.data))
        max_x = str(len(self.data[0]))
        max_yx = yx_str.format(max_y, max_x)
        
        if self.header_offset != self.header_offset_orig:
            # Hide column labels if header row disabled    
            max_width = min(int(self.max_x * .5), len(max_yx))
        else:
            #label = label_str.format('-', self.header[xp])
            max_width = min(int(self.max_x * .5), len(max_yx))
        yx = yx_str.format(yp + 1, xp + 1)
        #pad = " " * (max_width - len(yx) )
        #all = "{}{}".format(yx, pad)
        all = "{}".format(yx)
        if len(all) > max_width:
            all = all[:max_width - 1] + self.trunc_char
        
        return all

    
        


    def display(self):
        """Refresh the current display"""
        yp = self.y + self.win_y 
        xp = self.x + self.win_x
        

        # Print the current cursor cell in the top left corner
        self.scr.move(0, 0)
        self.scr.clrtoeol()
        #info = " {}".format(self.location_string(yp, xp))
        
        
        strhelp = "Press F1 for Help"
    
        cl=u"(\u2184) ESS - 2021".encode("utf-8")
        self.addstr(self.scr, 1, int(self.max_x/2),self.Title,curses.A_UNDERLINE+curses.A_BOLD)
        self.addstr(self.scr, 2, int(self.max_x/2)+1,cl,curses.A_BOLD)
        self.addstr(self.scr, 1, self.max_x - len(strhelp) - 1 ,strhelp,curses.A_REVERSE)
        # Adds the current cell content after the 'current cell' display
        #wc = self.max_x - len(info) - 2
        #s = self.cellstr(yp, xp, wc)
        #addstr(self.scr, "  " + s, curses.A_NORMAL)

        # Print a divider line
        self.scr.hline(5, 0, curses.ACS_HLINE, self.max_x)

        # Print the header if the correct offset is set
        if self.header_offset == self.header_offset_orig:
            self.scr.move(self.header_offset - 1, 0)
            self.scr.clrtoeol()
            for x in range(0, self.vis_columns):
                xc, wc = self.column_xw(x)
                s = self.hdrstr(x + self.win_x, wc)
                if x == self.x :
                    hattr = curses.A_BOLD+curses.A_UNDERLINE+curses.A_STANDOUT
                else:
                    hattr = curses.A_BOLD+curses.A_UNDERLINE
                self.addstr(self.scr, self.header_offset - 1, xc, s, hattr)

        # Print the table data
        for y in range(0, self.max_y - self.header_offset -
                       self._input_win_open ):
            yc = y + self.header_offset
            self.scr.move(yc, 0)
            self.scr.clrtoeol()
            for x in range(0, self.vis_columns):
                if x == self.x and y == self.y and self.searchres:
                    attr = curses.A_STANDOUT + curses.color_pair(2)
                    self.searchres = False
                elif y == self.y:
                    attr = curses.A_STANDOUT
                else:
                    attr = curses.A_NORMAL
                xc, wc = self.column_xw(x)
                s = self.cellstr(y + self.win_y, x + self.win_x, wc)
                if yc == self.max_y - 1 and x == self.vis_columns - 1:
                    # Prevents a curses error when filling in the bottom right
                    # character
                    self.insstr(self.scr, yc, xc, s, attr)
                else:
                    self.addstr(self.scr, yc, xc, s, attr)
                    

        totrow = "Tot Rows/Cols: " + str((len(self.data), self.num_data_columns))
        currpos = "Curr Row/Col: (%s,%s)    " % (yp + 1, xp + 1)
        self.addstr(self.scr,2,0,"Legend:",curses.A_UNDERLINE)
        self.addstr(self.scr,3,0,"******: Skip Naming API Validation Check",curses.A_NORMAL)
        self.addstr(self.scr,4,0,"------: Not Registered/Wrong Format",curses.A_NORMAL)
        self.addstr(self.scr,4,self.max_x - len(totrow) - 30  , currpos ,curses.A_NORMAL) 
        self.addstr(self.scr,4,self.max_x - len(totrow) - 1, totrow,curses.A_NORMAL)
        self.scr.refresh()

    def save_csvfile(self):
        save2 = curses.newwin(3, self.max_x -100, self.max_y - 3, 0)
        save3 = save2.derwin(1, self.max_x - 120, 1, 16)
        save2.box()
        save2.move(1, 1)
        self.addstr(save2, "Save csv file: ")
        save2.refresh()
        curses.curs_set(1)
        
        self.textpad = Textbox(save3, insert_mode=True)
        self.save_str = self.textpad.edit(self._input_validator)
        self.save_str = self.save_str.strip()
        try:
            curses.curs_set(0)
        except _curses.error:
            pass
    
        
        
        if self.save_str:
            it = []
            j = []
            if self.header_offset == self.header_offset_orig:
                for x in range(0, self.num_data_columns):
                    
                    s = self.header[x + self.win_x]
                    j.append(s.strip())
            j.append(self.summarytitle)
            j.append(self.ioctitle)
            it.append(j)
        
            for y in range(0, len(self.data)):
                #yc = y + self.header_offset
                j = []
                for x in range(0, self.num_data_columns):
                    
                    s = self.data[y + self.win_y][x + self.win_x]
                    j.append(s.strip())
                d = self.data[y + self.win_y][6]
                j.append(self.datainfo[d])
                if ( y == 0):
                    j.append(self.info)
                it.append(j)
            

            with open(self.save_str, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(it)


    def strpad(self, s, width):
        
        if width < 1:
            return str()
        if '\n' in s:
            s = s.replace('\n', '\\n')

        # take into account double-width characters
        buf = str()
        buf_width = 0
        for c in s:
            if sys.version_info.major == 2:
                c = c.decode('utf-8')
            w = 2 if unicodedata.east_asian_width(c) == 'W' else 1
            if buf_width + w > width:
                break
            buf_width += w
            buf += c

        if len(buf) < len(s):
            # truncation occurred
            while buf_width + len(self.trunc_char) > width:
                c = buf[-1]
                if sys.version_info.major == 2:
                    c = c.decode('utf-8')
                w = 2 if unicodedata.east_asian_width(c) == 'W' else 1
                buf = buf[0:-1]
                buf_width -= w
            buf += ' ' * (width - buf_width - len(self.trunc_char))
            buf += self.trunc_char
        elif buf_width < width:
            # padding required
            buf += ' ' * (width - buf_width)

        return buf

    def hdrstr(self, x, width):
        "Format the content of the requested header for display"
        if len(self.header) <= x:
            s = ""
        else:
            s = self.header[x]
        return self.strpad(s, width)

    def cellstr(self, y, x, width):
        "Format the content of the requested cell for display"
        if len(self.data) <= y or len(self.data[y]) <= x:
            s = ""
        else:
            s = self.data[y][x]
        return self.strpad(s, width)

    def _get_column_widths(self, width):
        """Compute column width array
        Args: width - 'max', 'mode', or an integer value
        Returns: [len of col 1, len of col 2, ....]
        """
        if width == 'max':
            self.column_width = self._get_column_widths_max(self.data)
        elif width == 'mode':
            self.column_width = self._get_column_widths_mode(self.data)
        else:
            try:
                width = int(width)
            except (TypeError, ValueError):
                width = 25
            self.column_width = [width for i in
                                 range(0, self.num_data_columns)]

    @staticmethod
    def __cell_len_dw(s):
        """Return the number of character cells a string will take
        (double-width aware). Defined as self._cell_len in __init__
        """
        len = 0
        for c in s:
            if sys.version_info.major == 2:
                c = c.decode('utf-8')
            w = 2 if unicodedata.east_asian_width(c) == 'W' else 1
            len += w
        return len

    def _mode_len(self, x):
        """Compute arithmetic mode (most common value) of the length of each item
        in an iterator.
            Args: x - iterator (list, tuple, etc)
            Returns: mode - int.
        """
        lens = [self._cell_len(i) for i in x]
        m = Counter(lens).most_common()
        # If there are a lot of empty columns, use the 2nd most common length
        # besides 0
        try:
            mode = m[0][0] or m[1][0]
        except IndexError:
            mode = 0
        max_len = max(lens) or 1
        diff = abs(mode - max_len)
        if diff > (self.column_gap * 2) and diff / max_len > 0.1:
            return max(max(1, self.column_gap), mode)
        else:
            return max(max(1, self.column_gap), max_len)

    def _get_column_widths_mode(self, d):
        """Given a list of lists, return a list of the variable column width
        for each column using the arithmetic mode.
        Args: d - list of lists with x columns
        Returns: list of ints [len_1, len_2...len_x]
        """
        d = zip(*d)
        return [self._mode_len(i) for i in d]

    def _get_column_widths_max(self, d):
        """Given a list of lists, return a list of the variable column width
        for each column using the max length.
        Args: d - list of lists with x columns
        Returns: list of ints [len_1, len_2...len_x]
        """
        d = zip(*d)
        return [max(1, min(250, max(set(self._cell_len(j) for j in i))))
                for i in d]

    def _skip_to_value_change(self, x_inc, y_inc):
        m = self.consume_modifier()
        for _ in range(m):
            x = self.win_x + self.x
            y = self.win_y + self.y
            v = self.data[y][x]
            y += y_inc
            x += x_inc
            while y >= 0 and y < len(self.data) \
                    and x >= 0 and x < self.num_data_columns \
                    and self.data[y][x] == v:
                y += y_inc
                x += x_inc
            self.goto_yx(y + 1, x + 1)

    def skip_to_row_change(self):
        self._skip_to_value_change(0, 1)

    def skip_to_row_change_reverse(self):
        self._skip_to_value_change(0, -1)

    def skip_to_col_change(self):
        self._skip_to_value_change(1, 0)

    def skip_to_col_change_reverse(self):
        self._skip_to_value_change(-1, 0)

#################################################
class TextBox:
    """Display a scrollable text box in the bottom half of the screen.
    """
    def __init__(self, scr, data='', title=""):
        self._running = False
        self.scr = scr
        self.data = data
        self.title = title
        self.tdata = []    # transformed data
        self.hid_rows = 0  # number of hidden rows from the beginning
        self.setup_handlers()

    def addstr(self,*args):
        scr, args = args[0], args[1:]
        return scr.addstr(*args)



    def __call__(self):
        self.run()

    def setup_handlers(self):
        self.handlers = {'\n': self.close,
                         curses.KEY_ENTER: self.close,
                         'q': self.close,
                         curses.KEY_RESIZE: self.close,
                         curses.KEY_DOWN: self.scroll_down,
                         'j': self.scroll_down,
                         curses.KEY_UP: self.scroll_up,
                         'k': self.scroll_up,
                         }

    def _calculate_layout(self):
        """Setup popup window and format data. """
        self.scr.touchwin()
        self.term_rows, self.term_cols = self.scr.getmaxyx()
        self.box_height = self.term_rows - int(self.term_rows / 2) 
        self.win = curses.newwin(int(self.term_rows / 2),
                                 self.term_cols, self.box_height, 0)
        try:
            curses.curs_set(False)
        except _curses.error:
            pass
        # transform raw data into list of lines ready to be printed
        s = self.data.splitlines()
        s = [wrap(i, self.term_cols - 3, subsequent_indent=" ") or [""] for i in s]
        self.tdata = [i for j in s for i in j]
        # -3 -- 2 for the box lines and 1 for the title row
        self.nlines = min(len(self.tdata), self.box_height - 3)
        self.scr.refresh()

    def run(self):
        self._running = True
        self._calculate_layout()
        while self._running:
            self.display()
            c = self.scr.getch()
            self.handle_key(c)

    def handle_key(self, key):
        if 0 < key < 256:
            key = chr(key)
        try:
            self.handlers[key]()
        except KeyError:
            pass

    def close(self):
        self._running = False

    def scroll_down(self):
        if self.box_height - 3 + self.hid_rows <= len(self.tdata):
            self.hid_rows += 1
        self.hid_rows = min(len(self.tdata), self.hid_rows)

    def scroll_up(self):
        self.hid_rows -= 1
        self.hid_rows = max(0, self.hid_rows)

    def display(self):
        self.win.erase()
        self.addstr(self.win, 1, 1, self.title[:self.term_cols - 3],
               curses.A_STANDOUT)
        visible_rows = self.tdata[self.hid_rows:self.hid_rows +
                                  self.nlines]
        
        self.addstr(self.win, 2, 1, '\n '.join(visible_rows))
        #if self.hid_rows:
        #    self.addstr(self.win, 1, self.term_cols-10, 'S',curses.A_REVERSE)
            



        if len(self.tdata) > (self.box_height - 1):
            self.addstr(self.win, self.nlines , self.term_cols-11, '--SCROLL--',curses.A_REVERSE)
            #if  self.nlines == len(visible_rows):
            #    self.addstr(self.win, self.nlines , self.term_cols-10, 'SCROLL D',curses.A_REVERSE)
        #        self.addstr(self.win, self.nlines , self.term_cols-2, 'v',curses.A_REVERSE)

        self.win.box()
        self.win.refresh()

    


####################################






    





def main(stdscr, *args, **kwargs):
    try:
        curses.start_color()
        curses.use_default_colors()
        for i in range(0, curses.COLORS):
            curses.init_pair(i + 1, i, -1)
    except (AttributeError, _curses.error):
        pass
    try:
        curses.curs_set(False)
    except (AttributeError, _curses.error):
        pass
    Viewer(stdscr, *args, **kwargs).run()


def view(data, start_pos=(0, 0), column_width=20, column_gap=3,
         trunc_char='…', column_widths=None, search_str=None,
         double_width=False, info=None,Title='',datainfo=None,sumtitle=None,ioctitle=None,readme=''
         ):
    """The curses.wrapper passes stdscr as the first argument to main +
    passes to main any other arguments passed to wrapper. Initializes
    and then puts screen back in a normal state after closing or
    exceptions.
    Args:
        data: data (list of lists or tuple of tuples).
              Should be normalized to equal row lengths
        
        start_pos: initial file position. Either a single integer for just y
            (row) position, or tuple/list (y,x)
        column_width: 'max' (max width for the column),
                      'mode' (uses arithmetic mode to compute width), or
                      int x (x characters wide). Default is 'mode'
        column_gap: gap between columns
        column_widths: list of widths for each column [len1, len2, lenxxx...]
        trunc_char: character to indicate continuation of too-long columns
        search_str: string to search for
        double_width: boolean indicating whether double-width characters
                      should be handled (defaults to False for large files)
        info: Data information to be displayed on ^g. For example a variable
              name or description of the current data. 
              Title: The name of the application
        datainfo:
        sumtitle:
        ioctitle:
        readme:
    """
    lc_all = None
    if info is None:
        info = ""
    try:
        
        while True:
            try:
                
                if len(data) == 1 and b'\r' in data[0]:
                    data = data[0].split(b'\r')

   
                max_len = set((len(i) for i in data))
                if len(max_len) != 1:
                    max_len = max(max_len)
                    data = [i + [""] * (max_len - len(i)) for i in data]

                
                

                curses.wrapper(main, data,
                               start_pos=start_pos,
                               column_width=column_width,
                               column_gap=column_gap,
                               trunc_char=trunc_char,
                               column_widths=column_widths,
                               search_str=search_str,
                               double_width=double_width,
                               info=info,
                               datainfo=datainfo,
                               Title=Title,
                               sumtitle=sumtitle,
                               ioctitle=ioctitle,
                               readme=readme)
                
                               



            except (QuitException, KeyboardInterrupt):
                return 0
            except ReloadException as e:
                start_pos = e.start_pos
                column_width = e.column_width_mode
                column_gap = e.column_gap
                column_widths = e.column_widths
                search_str = e.search_str
                continue
    finally:
        if lc_all is not None:
            locale.setlocale(locale.LC_ALL, lc_all)



