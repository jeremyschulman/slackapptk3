import re
from textwrap import TextWrapper


class TextBlockWrapper(TextWrapper):
    """
    TextBlockWrapper creates chunks where the text blocks are designated
    by a newline followed by a non-space charaacter.  For exampele,
    the following will create chunks so that the text of "VLAN Blue"
    is a chunk, and "VLAN Red" is another chunk.

    Example
    -------
    VLAN  Name                             Status    Ports
    ----- -------------------------------- --------- -------------------------------
    132   Blue                             active    Cpu, Po1, Po2, Po3, Po4, Po5
                                                     Po6, Po7, Po8, Po9, Po10, Po11
                                                     Po12, Po13, Po53, Po54, Po2000
                                                     Vx1
    133   Red                              active    Cpu, Po1, Po2, Po3, Po4, Po5
                                                     Po6, Po7, Po8, Po9, Po10, Po11
                                                     Po12, Po13, Po53, Po54, Po2000
                                                     Vx1

    For use with Slack Section Blocks, there is a max text length of 3000 characters.
    To create text blocks that would map into SectionBlock:

        # string output > 3000 bytes
        my_device_output = "...some long text string..."

        wr = TextBlockWrapper(
            width=3000,
            break_long_words=False,
            replace_whitespace=False)

        # list of text blocks each max len 3000
        text_blocks = wr.wrap(my_device_output)
    """
    sentence_end_re = re.compile(r'(\n)(?=\S)')

    def _split_chunks(self, text):
        return self.sentence_end_re.split(text)
