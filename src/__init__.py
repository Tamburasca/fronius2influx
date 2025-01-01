"""
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

"""
How to use CIPHER:
OS environmental variable 'MOSQUITTO_CIPHER' (required) containing the cipher
key to en-/decrypt the wattpilot access password. Run following commands 
in python3
>>> from cryptography.fernet import Fernet
>>> mosquitto_cipher = Fernet.generate_key() # if key exists, skip this line
>>> cipher_suite = Fernet(b'mosquitto_cipher')
>>> application_key_encrypt = cipher_suite.encrypt(b'password')
"""

__author__ = "Dr. Ralf Antonius Timmermann"
__copyright__ = ("Copyright (c) 2023-2025, Dr. Ralf Antonius Timmermann "
                 "All rights reserved.")
__credits__ = ""
__license__ = "BSD-3-Clause"
__version__ = "1.0.0"
__maintainer__ = "Dr. Ralf Antonius Timmermann"
__email__ = "ralf.timmermann@gmx.de"
__status__ = "Prod"
