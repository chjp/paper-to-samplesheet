import retrieve_ncbi


BIOSAMPLE_XML = b"""<BioSampleSet>
  <BioSample accession="SAMN14407001">
    <Ids><Id db="BioSample">SAMN14407001</Id></Ids>
    <Attributes>
      <Attribute attribute_name="sample_name">T54</Attribute>
      <Attribute attribute_name="host">Homo sapiens</Attribute>
    </Attributes>
  </BioSample>
</BioSampleSet>"""


SRA_XML = """<EXPERIMENT_PACKAGE>
  <EXPERIMENT accession="SRX001">
    <PLATFORM><ILLUMINA/></PLATFORM>
    <DESIGN><LIBRARY_DESCRIPTOR>
      <LIBRARY_STRATEGY>AMPLICON</LIBRARY_STRATEGY>
      <LIBRARY_SOURCE>GENOMIC</LIBRARY_SOURCE>
      <LIBRARY_SELECTION>PCR</LIBRARY_SELECTION>
    </LIBRARY_DESCRIPTOR></DESIGN>
  </EXPERIMENT>
  <SAMPLE accession="SAMN14407001"/>
  <EXTERNAL_ID namespace="BioProject">PRJNA613586</EXTERNAL_ID>
  <RUN_SET><RUN accession="SRR11355982"/></RUN_SET>
</EXPERIMENT_PACKAGE>"""


def test_parse_biosample_xml():
    biosamples = retrieve_ncbi.parse_biosample_xml(BIOSAMPLE_XML)

    assert biosamples[0]["accession"] == "SAMN14407001"
    assert biosamples[0]["attributes"]["sample_name"] == "T54"


def test_parse_sra_xml():
    runs = retrieve_ncbi.parse_sra_xml(SRA_XML)

    assert runs[0]["run_accession"] == "SRR11355982"
    assert runs[0]["biosample_accession"] == "SAMN14407001"
    assert runs[0]["library_strategy"] == "AMPLICON"
