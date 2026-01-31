# bedclock
#### Python based controller for RGB led matrix, running in a Raspberry Pi

## A Brief Explanation

My bedside clock got pushed to the floor and I kept losing track of time.

![Old bedside clock](https://live.staticflickr.com/1855/29633788337_ae9a5f06e6_w.jpg)

So I decided to build one and hang it on the headboard. This repo captures
the main steps I took.

![RGB LED Matrix clock](https://farm2.staticflickr.com/1923/29916857047_9f3a571fc8_z.jpg)

You can see more pictures related to this project using [this link :art:](https://www.flickr.com/gp/38447095@N00/705C56)

## Blog on Adafruit

This README has been ported to Adafruit's learn page. If you prefer that format, here is the link for it:
**[https://learn.adafruit.com/motion-controlled-matrix-bed-clock](https://learn.adafruit.com/motion-controlled-matrix-bed-clock)**

## Hardware

#### The main hardware components used:

* [Raspberry Pi Zero W](https://www.adafruit.com/product/3400)
* 8GB MicroSD Card
* [Adafruit RGB Matrix Bonnet for Raspberry Pi](https://www.adafruit.com/product/3211)
* [64x64 RGB LED Matrix - 2.5mm Pitch](https://www.adafruit.com/product/3649)
* [Adafruit APDS9960 Proximity, Light, RGB, and Gesture Sensor](https://www.adafruit.com/product/3595)
* [5V 10A switching power supply](https://www.adafruit.com/product/658)
* **Optional:** [Console Cable for Raspberry Pi](https://www.adafruit.com/product/954)

**All of the parts can be purchased at [my favorite DIY store (aka Adafruit)](https://adafruit.com)**

For building the frame that holds the clock, I took the 3D printing route.
The first generation was done using [Autodesk Tinkercad](https://www.tinkercad.com/things/7wOHX7GfFme).
That is posted in [thingiverse.com](https://www.thingiverse.com/thing:3070573). While shopping for places to print it,
I was shocked with the price estimates and ended up abandoning that idea. :hurtrealbad: The high
cost was mostly associated with my naiveness with the design. Thankfully, I got help from a [CAD guru](https://www.linkedin.com/in/thebrianbailey/), 
who split the harness into 2 parts for better rendering. [Brian](https://github.com/bunedoggle) was also kind enough to print it for me.
To say that this dude is freaking amazingly awesome is an understatement. :bow:

The frame we ended up using for the clock was done using [OnShape](https://cad.onshape.com/) and you can
[get there using this link](https://cad.onshape.com/documents/28baa48f25d4dc6e6211634d/v/d9f02a67fde16e56652c7566/e/8044c64ece9d04910adc8c90).
The [.STL](https://www.thingiverse.com/thing:3140714/files) file is also [available on thingiverse.com](https://www.thingiverse.com/thing:3140714/zip).

## Software

#### Installation

###### Install Rapsbian-Lite on RPI

There are lots of info on how to do that already, so you should be able to [google for that](https://lmgtfy.com/?q=install+raspbian+lite) and use your favorite. [Try this link](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi#prerequisite-pi-setup-2-3) if you are feeling lucky. :smirk:

Instead of hooking up the RPI to a screen and keyboard, I used its serial port to connect to the console. In order to do that, make sure to
add this line to the file **/boot/config.txt**

```
enable_uart=1
```

Connect using the **115200.8.N.1** parameters. You can read more about how to [do that here](https://learn.adafruit.com/raspberry-pi-zero-creation/enable-uart).
I use the [Prolific USB serial adapter](https://www.adafruit.com/product/954) but there
are many choices out there. There is a nice [article on doing this at learn.adafruit.com](https://learn.adafruit.com/adafruits-raspberry-pi-lesson-5-using-a-console-cable?view=all). Just know that once you configure an IP address and SSH access to your RPI, you will not need this connection.

As part of my Raspbian installation, I did the following:

`sudo raspi-config`

* Network Options -> Wi-fi
* Localisation Options -> change timezone
* Interfacing Options -> enable ssh
* Interfacing Options -> enable I2C  (needed for motion sensor)


###### Install the code that controls the RGB display

Simply read and take all the steps mentioned in the awesome [page that Ladyada wrote on this](https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi?view=all). :warning: There is lots of important information in that document, so take your time and read it carefully!

Once you get the hardware part done, this is what you need to run:

```
sudo apt-get install -y git i2c-tools \
  python3-dev python3-pillow python3-setuptools cython3

cd && \
curl https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/rgb-matrix.sh >rgb-matrix.sh
sudo bash rgb-matrix.sh  ; # wait a while and reboot
```

At this point, you should be able to run the demos that are added as part of the [hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) install. For example:

```
cd ~/rpi-rgb-led-matrix/examples-api-use

ROTATE=180
TIMEOUT='10s'
PARAMS='--led-rows=64 --led-cols=64 --led-brightness=88'
PARAMS+=' --led-gpio-mapping=adafruit-hat'
for X in 0 {3..11} ; do \
     sudo timeout ${TIMEOUT} \
          ./demo ${PARAMS} --led-pixel-mapper="Rotate:${ROTATE}" -D${X}
     sleep 0.3
done
```

Create a .pth file so Python always includes a path to rgbmatrix

```
SITE_DIR="$(sudo python3 -c 'import site; print(site.getsitepackages()[0])')"

[ -n "$SITE_DIR" ] && \
  echo "/home/pi/rpi-rgb-led-matrix/bindings/python" | \
    sudo tee "${SITE_DIR}/rgbmatrix.pth" >/dev/null

sudo python3 -c 'import rgbmatrix; print("ok:", rgbmatrix)' || echo FAILED
```

###### Remove/disable unnecessary services

RPI Zero W handles the display just fine but it does not hurt to help it out by disabling unused things that compete for cycles.
These were the ones I did on my setup, based on 
[Henner](https://github.com/hzeller/rpi-rgb-led-matrix/tree/814b79b5696d32dd1140304b41a1ec0068bb271a#use-minimal-raspbian-distribution)'s advice:

```
sudo systemctl disable --now avahi-daemon avahi-daemon.socket && \
sudo apt-get remove -y bluez bluez-firmware && \
echo ok
```

###### Install core python libraries to control the motion and light sensor

Follow the [steps documented here](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux?view=all#circuitpython-on-linux-and-raspberry-pi-1-5) to install CircuitPython on Raspberry Pi.

The commands I used were:

```
sudo apt-get install -y i2c-tools

# Ensure i2c device is present
ls /dev/i2c*  && echo ok || echo bad error cannot see i2c
```

###### Clone this repo inside the RPI and install the remainder packages

You are almost there! At this point, we just need to grab the packages listed in the **[requirements.txt](requirements.txt)** file.

```
sudo apt-get install -y python3-pip git

BRANCH=adafruit
cd && \
git clone -b ${BRANCH} https://github.com/flavio-fernandes/bedclock.git  bedclock.git


cd ~/bedclock.git && sudo -H pip3 install --break-system-packages --upgrade -r ./requirements.txt
```

Install and enable systemd service, which will start bedclock application automatically upon reboot:

```
sudo cp -v ~/bedclock.git/bedclock/bin/bedclock.service /lib/systemd/system/
sudo systemctl enable bedclock.service

# start the application
sudo systemctl start bedclock.service
```

You can monitor what is happening with the app by looking at the log or
*systemd status*:

```
sudo systemctl status bedclock.service

sudo journalctl -u bedclock.service --follow
```

###### Customize

There are lots of knobs that can be tweaked to make the clock behave
as you want. Most of these settings are located in the file called
**[const.py](bedclock/const.py)**. After making the changes, make sure to
restart the application by typing the following command:

```
sudo systemctl restart bedclock.service
```

If you want to start it manually, use **[start_bedclock.sh](bedclock/bin/start_bedclock.sh)**:

```
sudo systemctl stop bedclock.service
~/bedclock.git/bedclock/bin/start_bedclock.sh
```

#### MQTT

If you have an [MQTT](https://learn.adafruit.com/adafruit-io/mqtt-api) broker that your
bedclock can talk to, you can enable it via the `mqtt_enabled` knob in
the **[const.py](bedclock/const.py)** file. Here are the commands I use to see these events:

###### Receiving events published by the bedclock application

```bash
# Install mqtt client to poke bedclock via mqtt broker
$ sudo apt-get install -y mosquitto-clients

$ mosquitto_sub -v -h ${MQTT_BROKER} -t "/bedclock/motion" -t "/bedclock/light"
/bedclock/motion on
/bedclock/motion off
/bedclock/light 365
```

###### Configuring the clock to stay awake in the dark

If you don't want the clock to go blank when the room is dark, you can change its default
behavior in **[const.py](bedclock/const.py)** by 
setting `scr_stayOnInDarkRoomDefault = True`. Or via MQTT, as shown below:

```bash
$ mosquitto_pub -h ${MQTT_BROKER} -t /bedclock/stay -r -m "on"
$ mosquitto_pub -h ${MQTT_BROKER} -t /bedclock/stay -r -m "off"

# to clear topic from broker and use const.scr_stayOnInDarkRoomDefault
$ mosquitto_pub -h ${MQTT_BROKER} -t /bedclock/stay -r -n
```

#### YouTube Demo

[![Bedclock Demo](https://img.youtube.com/vi/kgT8Nts2mAI/0.jpg)](https://www.youtube.com/watch?v=kgT8Nts2mAI "Bedclock Demo")

[![Show-and-Tell Adafruit](https://img.youtube.com//vi/2VQixyqWGfE/0.jpg)](https://youtu.be/2VQixyqWGfE?t=584 "Bedclock Adafruit Show-and-Tell")

#### TODO  :construction:

* Expose knobs to make MQTT use SSL
* Display weather :partly_sunny:
* Add alarm :alarm_clock:
* Add monitoring  :boom: :exclamation:
* Add fun animations
* Make a cover for RPI on the backside
