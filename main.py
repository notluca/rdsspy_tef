import serial, socket
import time

picode = ""

def read_from_serial(port='COM3', baudrate=115200, timeout=0.1):
    global picode
    
    tcp_server = None #
    try:
        with serial.Serial(port, baudrate, timeout=timeout) as ser:
            print(f"Connected to {port} at {baudrate} baud.")
            time.sleep(2)  


            tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_server.bind(('0.0.0.0', 7373))  
            tcp_server.listen(1)
            print("TCP server listening on port 7373")


            ser.write('x\n'.encode('utf-8'))
            ser.write('Q0\n'.encode('utf-8'))
            ser.write('M0\n'.encode('utf-8'))
            ser.write(f'Z0\n'.encode('utf-8'))  
            conn = None
            tcp_server.settimeout(0.01) 

            while True:
                if not conn:
                    try:
                        conn, addr = tcp_server.accept()
                        print(f"Connected by {addr}")
                        conn.settimeout(None) 
                    except socket.timeout:
                        pass
                    except socket.error as e:
                        print(f"TCP server accept error: {e}")
                        break 
                
                if conn:
                    try:
                        conn.setblocking(False)
                        data = conn.recv(1024)
                        if not data:
                            print("TCP client disconnected.")
                            conn.close()
                            conn = None
                        else:
                            command_str = data.decode('utf-8', errors='ignore').strip()
                            if command_str.endswith('*F'):
                                try:
                                    freq_part = command_str[:-2]
                                    freq_khz = int(freq_part)
                                    print(f"Tuning to {freq_khz / 1000.0} MHz")
                                    ser.write(f'T{freq_khz}\n'.encode('utf-8'))
                                except (ValueError, IndexError):
                                    print(f"Invalid frequency command received: {command_str}")
                    except BlockingIOError:
                        pass
                    except socket.error as e:
                        print(f"TCP receive error: {e}")
                        conn.close()
                    finally:
                        if conn:
                            conn.setblocking(True)

                while ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').rstrip()
                    if not line:
                        continue
                    
                    first_char = line[0]
                    if first_char == "P":
                        picode = line[1:]
                    
                    elif first_char == "R" and conn: 
                        modified_data = line[1:]

                        if len(modified_data) == 14:
                            errors_new = 0
                            pi = '0000'

                            if picode and len(picode) >= 4:
                                pi = picode[:4]
                                errors_new = (len(picode) - 4) << 6
                            else:
                                errors_new = (0x03 << 6)

                            errors_old = int(modified_data[12:], 16)
                            errors_new |= (errors_old & 0x03) << 4
                            errors_new |= (errors_old & 0x0C)
                            errors_new |= (errors_old & 0x30) >> 4

                            modified_data = pi + modified_data[:12]
                            modified_data += format(errors_new, '02x')

                        picode = ""

                        try:
                            errors = int(modified_data[-2:], 16)
                            data_to_send = ""
                            data_to_send += modified_data[0:4] if (errors & 0xC0) == 0 else '----'
                            data_to_send += modified_data[4:8] if (errors & 0x30) == 0 else '----'
                            data_to_send += modified_data[8:12] if (errors & 0x0C) == 0 else '----'
                            data_to_send += modified_data[12:16] if (errors & 0x03) == 0 else '----'

                            final_string = f"G:\r\n{data_to_send}\r\n\r\n"
                            conn.sendall(final_string.encode('utf-8'))
                        except (socket.error, IndexError, ValueError) as e:
                            print(f"Error sending data over TCP: {e}")
                            conn.close()
                            conn = None

                if ser.in_waiting == 0:
                    time.sleep(0.01)

    except serial.SerialException as e:
        print(f"Error: {e}")
    finally:
        if tcp_server:
            tcp_server.close()
            print("TCP server closed.")

read_from_serial()
