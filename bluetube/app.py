#!/usr/bin/python3

'''
    This file is part of Bluetube.

    Bluetube is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Bluetube is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Bluetube.  If not, see <https://www.gnu.org/licenses/>.
'''

import argparse

from bluetube import Bluetube, __version__
from bluetube.model import OutputFormatType


def main():

    def add(bluetube, args):
        profiles = args.profiles if args.profiles else ['profile_1']
        bluetube.add_playlist(args.url,
                              OutputFormatType.from_char(args.type),
                              profiles)

    description = 'The script downloads youtube video as video or audio, ' \
                  'converts and sends to a destination.'
    epilog = 'If no option specified the script shows feeds to choose, ' \
             'downloads and processes according to the profile.'
    parser = argparse.ArgumentParser(prog='bluetube', description=description)
    parser.epilog = epilog

    subparsers = parser.add_subparsers(title='Commands',
                                       description='Use the commands below to '
                                       'modify or show subscribed playlists.',
                                       help='')

    parser_add = subparsers.add_parser('add',
                                       help='add a URL to bluetube')
    parser_add.add_argument('url', type=str,
                            help="an playlist's URL")
    parser_add.add_argument('-t', dest='type',
                            choices=['a', 'v'],
                            default='v',
                            help='a type of a file you want to get; '
                                 '(a)udio or (v)ideo')
    parser_add.add_argument('-p', nargs='*',
                            dest='profiles',
                            help='one or multiple profiles')
    parser_add.set_defaults(func=add)

    parser_list = subparsers.add_parser('list',
                                        help='list all playlists')
    parser_list.set_defaults(func=lambda bt, _: bt.list_playlists())

    parser_remove = subparsers.add_parser('remove',
                                          help='remove a playlist by names '
                                               'of the author and '
                                               'the playlist')
    parser_remove.add_argument('--author', '-a',
                               type=str,
                               help='an author of a playlist to be removed')
    parser_remove.add_argument('--playlist', '-p',
                               type=str,
                               help='a playlist to be removed')
    parser_remove.set_defaults(func=lambda bt, args:
                               bt.remove_playlist(args.author.strip(),
                                                  args.playlist.strip())
                               if args.author and args.playlist
                               else parser.print_usage())

    parser_edit = subparsers.add_parser('edit',
                                        help='edit a playlist')
    parser_edit.add_argument('--author', '-a',
                             type=str,
                             required=True,
                             help='an author of a playlist to edit')
    parser_edit.add_argument('--playlist', '-p',
                             type=str,
                             required=True,
                             help='a playlist to edit')
    parser_edit.add_argument('--output-type', '-t',
                             choices=['a', 'v'],
                             help='a type of a file you want to get;'
                                  '(a)udio or (v)ideo')
    parser_edit.add_argument('--profiles', '-pr',
                             nargs='*',
                             help='a list of profiles for this playlist')
    parser_edit.add_argument('--reset-failed', '-r',
                             action='store_true',
                             help='discard previously failed videos')
    parser_edit.add_argument('--days-back', '-d',
                             type=int,
                             metavar='N',
                             help='move last update date to N days back')
    parser_edit.set_defaults(func=lambda bt, args:
                             bt.edit_playlist(args.author.strip(),
                                              args.playlist.strip(),
                                              OutputFormatType
                                              .from_char(args.output_type),
                                              args.profiles,
                                              args.reset_failed,
                                              args.days_back))

    me_group = parser.add_mutually_exclusive_group()

    me_group.add_argument('--send', '-s',
                          help='send already downloaded files',
                          action='store_true')

    me_group.add_argument('--edit_profiles', '-p',
                          action='store_true',
                          help='edit profiles in a text editor')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='print more information')
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {__version__}')

    args = parser.parse_args()
    bluetube = Bluetube(args.verbose)
    if hasattr(args, 'func'):
        args.func(bluetube, args)
    else:
        if args.send:
            bluetube.send()
        elif args.edit_profiles:
            bluetube.edit_profiles()
        else:
            bluetube.run()


if __name__ == '__main__':
    main()
