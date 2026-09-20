import unittest

from tools.capture_blackmagic_monitor import monitor,ports,links


class BlackmagicMonitorTests(unittest.TestCase):
    def node(self,name='blackmagic'):
        return dict(id=10,type='PipeWire:Interface:Node',info=dict(props={
            'application.name':'OBS','media.name':name,'media.class':'Stream/Output/Audio'}))

    def port(self,channel,identifier):
        return dict(id=identifier,type='PipeWire:Interface:Port',info=dict(props={
            'node.id':10,'port.direction':'out','audio.channel':channel}))

    def test_only_exact_blackmagic_stream_selected(self):
        desired=self.node()
        self.assertEqual(monitor([self.node('stream-radio'),desired]),desired)
        with self.assertRaises(ValueError):monitor([self.node('stream-radio')])

    def test_ambiguous_blackmagic_stream_rejected(self):
        with self.assertRaises(ValueError):monitor([self.node(),self.node()])

    def test_only_complete_unique_stereo_ports_accepted(self):
        stereo=[self.port('FL',11),self.port('FR',12)]
        self.assertEqual(ports(stereo,10,'out'),dict(FL=11,FR=12))
        for bad in (stereo[:1],stereo+[self.port('FL',13)],stereo+[self.port('AUX0',13)]):
            with self.assertRaises(ValueError):ports(bad,10,'out')

    def test_existing_links_identified_by_source_not_desktop_sink(self):
        def link(source,port):return dict(type='PipeWire:Interface:Link',info={
            'output-node-id':source,'output-port-id':port,'input-node-id':30,'input-port-id':31})
        self.assertEqual(links([link(10,11),link(20,21)],10),[(11,30,31)])
