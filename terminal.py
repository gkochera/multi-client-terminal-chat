# Author: George Kochera
# Date: 3/12/2021
# Name: terminal.py
# Description: Used for flow control of the client application, process forking
# and GUI presentation.
# Sources: See README.md

import os, socket, curses
from multiprocessing import Process
import select
import random

# This variable holds all the strings which are the chat messages
chat_record = []

# This variable holds all the user settings by user, for now just colors
users = {}

# Global variable to make sure each user name gets a unique color
color_number = 3

# Adds the header to the screen object
def display_header(main_screen, name: str, curses=curses):

    # Grab the lines and columns of the window
    cols = curses.COLS

    # Setup our text, and add it to the screen always at 0, 0
    title = "Multi-Client Terminal Chat >> {}".format(name)
    padding = " " * 256
    header = title + padding
    main_screen.addnstr(0, 0, header, cols, curses.color_pair(1))


# Displays the chat element in the screen object
def display_chat(main_screen, curses=curses):

    # Write the updated elements to the chat window        
    global color_number

    # We alwasy want the chat window to start right above the input line
    newest = curses.LINES - 1

    # For each element in the chat_record, we write it to the chat window,
    # starting at the bottom, up to the top.
    for element in chat_record:
        
        # This is purely for colorization of the user name, we split the
        # Username: Text in to tokens, colorize the name so that its always the
        # same color for each user, and then write it to the screen along
        # with the text as the plain screen color

        # Detect a client generated message
        if element[:3] == "~!~":
            main_screen.addnstr(newest - 1, 0, element[3:], len(element[3:]), curses.color_pair(0))
            newest -= 1
        
        # Detect a received message
        else:
            tokens = element.split(":")
            user = tokens[0]
            text = ":".join(tokens[1:])
            if user not in users.keys():
                users[user] = color_number
                curses.init_pair(color_number, random.randint(0, 255), 0)
                color_number += 1

            # Add the colon back to the end of the username
            user_lead = user + ":"

            # Write the colorized username and text to the chat box and decrement
            # newest to start over again with the next line
            main_screen.addnstr(newest - 1, 0, user_lead, len(user_lead), curses.color_pair(users[user]))
            main_screen.addnstr(newest - 1, len(user) + 1, text, len(text), curses.color_pair(0))
            newest -= 1



# Just moves the blinking cursor to the lower left corner in front of the prompt
def set_cursor_home(main_screen, curses=curses):
    main_screen.addstr(curses.LINES - 1, 0, "> ", curses.color_pair(2))
    main_screen.move(curses.LINES - 1, 2)


# Must be called between each chat event or input event to update all the screen
# elements
def update_screen(main_screen, name: str):

    # Clear the screen completely
    main_screen.clear()

    # Add the header, updated chat box, set the cursor back to the input area
    # and call refresh which actually displays the contents
    display_header(main_screen, name)
    display_chat(main_screen)
    set_cursor_home(main_screen)
    main_screen.refresh()


# This function is run in its own process and constantly polls the socket for
# new messages. It then updates the screen when a new message is received.
def chat(main_screen, conn_socket: socket.socket, name: str, curses=curses):

    running = True
    while running:

        # Check to see if we got any new messages
        (rdy_to_read, _, _) = select.select([conn_socket],[],[])
        if rdy_to_read:

            # Read the data, convert it to a string, insert it in the chat record
            # If the chat record is too long, we remove the oldest messages that
            # wont fit on the screen
            received_data = conn_socket.recv(curses.COLS - 1)

            # Remotely closed sockets will continuously read as a 0 byte string
            # in Python, we detect this since we know normally we will always send
            # data one way or the other, and if this condition is met, we tell
            # the user the server disconnected.
            if received_data == b'':
                chat_record.insert(0, "~!~You have been disconnected from the server...")
                chat_record.insert(0, "~!~Enter '/q' to quit.")
                if len(chat_record) > curses.LINES - 2:
                    chat_record.pop()
                update_screen(main_screen, name)
                running = False
            
            # Otherwise, update the chat panel as normal
            else:
                received_string = str(received_data, 'UTF-8')
                chat_record.insert(0, received_string)
                if len(chat_record) > curses.LINES - 2:
                    chat_record.pop()

                # Update the screen
                update_screen(main_screen, name)


# Helpfer function to append the name of the current user to the message they
# sent
def format_message_string(sent_message: bytes, name: str):
    s_input = str(sent_message, 'UTF-8').strip()
    s_input = name + ": " + s_input
    return s_input


# This is the main input loop and controls the flow of the program for the 
# user inputting data and sending it to the server.
def run(main_screen, data_socket: socket.socket, name: str, curses=curses):
    running = True
    while running:
        
        # Display the updated screen with the cursor ready for input
        update_screen(main_screen, name)

        # Capture the input from the user clear it from the same line
        b_input = main_screen.getstr(curses.LINES - 1, 2)
        main_screen.clrtoeol()

        # Convert the input to a Python String
        s_input = format_message_string(b_input, name)

        # Look for the trigger to exit
        if '/q' in s_input:
            running = False
            message = "-~~{}~~-".format(name)
            data_socket.send(bytes(message, 'utf-8'))
            break

        # Send the data to the socket so the connected machine gets the message
        data_socket.send(bytes(s_input, 'utf-8'))


# This is the main entry point of the program and it is used to setup 
# curses for the gui, it is also used to fork off the two process required for
# the client, the chat box, and input cycle. It is also responsible for cleaning
# up and exiting safely when done.
def main(stdscr, data_socket: socket.socket, name: str):

    # Make sure we can see output from the user typing in the input field
    curses.echo(True)

    # Rename the stdscr to main_screen from curses.wrapper
    main_screen = stdscr

    curses.init_pair(1, 226, 58)
    curses.init_pair(2, 118, 0)
    
    # Spin up the input thread
    t_input = Process(target=run, args=(main_screen, data_socket, name))
    t_input.start()

    # Spin up the chat log thread
    t_chat = Process(target=chat, args=(main_screen, data_socket, name))
    t_chat.start()

    # Wait for the threads to finish and close
    t_input.join()
    t_chat.terminate()


# This is the loader for main, it adds a wrapper to the curses object so that
# we can keep the terminal tidy after exiting and helps with debugging.
def loader(data_socket: socket, name: str):
    curses.wrapper(main, data_socket, name)
    curses.endwin()